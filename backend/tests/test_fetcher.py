"""
Tests for app.scrapers.fetcher.preprocess_html.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.scrapers.fetcher import (
    CookiesExpiredError,
    SiteBlockedError,
    _is_blocked,
    fetch_page,
    fetch_with_stored_cookies,
    preprocess_html,
)


class TestPreprocessHtml:
    def test_strips_script_tags(self):
        html = "<html><body><script>var price = 99.99;</script><p>Hello</p></body></html>"
        result = preprocess_html(html)
        assert "var price" not in result
        assert "Hello" in result

    def test_strips_style_tags(self):
        html = "<html><body><style>.price { color: red; }</style><p>Content</p></body></html>"
        result = preprocess_html(html)
        assert ".price" not in result
        assert "Content" in result

    def test_strips_nav(self):
        html = "<html><body><nav>Home | About | Contact</nav><main>Product</main></body></html>"
        result = preprocess_html(html)
        assert "Home | About" not in result
        assert "Product" in result

    def test_strips_footer(self):
        html = "<html><body><p>Price: $99</p><footer>Copyright 2024</footer></body></html>"
        result = preprocess_html(html)
        assert "Copyright" not in result
        assert "Price" in result

    def test_strips_header(self):
        html = "<html><body><header>Site Logo</header><p>Main content</p></body></html>"
        result = preprocess_html(html)
        assert "Site Logo" not in result
        assert "Main content" in result

    def test_truncates_at_max_chars(self):
        long_content = "x" * 20000
        html = f"<html><body><p>{long_content}</p></body></html>"
        result = preprocess_html(html, max_chars=12000)
        assert len(result) <= 12000

    def test_empty_html_returns_empty_string(self):
        result = preprocess_html("")
        assert result == ""

    def test_removes_blank_lines(self):
        html = "<html><body><p>Line 1</p>\n\n\n<p>Line 2</p></body></html>"
        result = preprocess_html(html)
        lines = [l for l in result.splitlines() if not l.strip()]
        assert len(lines) == 0, "preprocess_html should remove blank lines"

    def test_next_data_script_is_stripped(self):
        """__NEXT_DATA__ contains all product data on Next.js sites — it's inside
        a <script> tag and must be stripped to avoid bloating the LLM context.
        (This is a known limitation; the price must come from meta tags or CSS selectors.)"""
        html = (
            '<html><head>'
            '<script id="__NEXT_DATA__" type="application/json">'
            '{"props":{"pageProps":{"product":{"price":128.00,"name":"Jackie Cardigan"}}}}'
            '</script>'
            '</head><body><p>See product above</p></body></html>'
        )
        result = preprocess_html(html)
        assert "128.00" not in result, "__NEXT_DATA__ prices are stripped; use meta tags or CSS selectors"
        assert "Jackie Cardigan" not in result


class TestBlockedAndCompleteSignals:
    @pytest.mark.parametrize("html", [
        "<html>Robot Check</html>",
        "<html>Access denied</html>",
        "<html>Please enable JavaScript and cookies</html>",
        "<html><div id='px-captcha'></div></html>",
    ])
    def test_is_blocked_true(self, html):
        assert _is_blocked(html) is True

    @pytest.mark.parametrize("html", [
        "<html><body><p>normal product content</p></body></html>",
        "<html><body><h1>shirt</h1><span>$29.99</span></body></html>",
    ])
    def test_is_blocked_false(self, html):
        assert _is_blocked(html) is False

    def test_is_blocked_rejects_blocked_page(self):
        html = ("x" * 6000) + " Robot Check "
        assert _is_blocked(html) is True


class TestFetchWithStoredCookies:
    @pytest.mark.asyncio
    async def test_returns_short_non_blocked_html_when_cookie_fetch_succeeds(self):
        class _Resp:
            status_code = 200
            text = "<html><body><h1>Product</h1><span>$19.99</span></body></html>"

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url):
                return _Resp()

        with patch("app.scrapers.fetcher.httpx.AsyncClient", return_value=_Client()):
            html = await fetch_with_stored_cookies("https://shop.example.com/p/1", {"sid": "abc"})

        assert "Product" in html

    @pytest.mark.asyncio
    async def test_raises_cookie_expired_on_403(self):
        class _Resp:
            status_code = 403
            text = "<html>forbidden</html>"

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url):
                return _Resp()

        with (
            patch("app.scrapers.fetcher.httpx.AsyncClient", return_value=_Client()),
            pytest.raises(CookiesExpiredError),
        ):
            await fetch_with_stored_cookies("https://shop.example.com/p/1", {"sid": "abc"})


class TestFetchPageRouting:
    @pytest.mark.asyncio
    async def test_uses_stored_cookies_first(self):
        with (
            patch("app.scrapers.fetcher.fetch_with_stored_cookies", new=AsyncMock(return_value="cookie-html")) as mock_cookies,
            patch("app.scrapers.fetcher.fetch_with_httpx", new=AsyncMock(return_value="httpx-html")) as mock_httpx,
            patch("app.scrapers.fetcher.fetch_with_playwright", new=AsyncMock(return_value="pw-html")) as mock_pw,
        ):
            result = await fetch_page("https://shop.example.com/p/1", stored_cookies={"sid": "abc"})

        assert result == "cookie-html"
        mock_cookies.assert_awaited_once()
        mock_httpx.assert_not_awaited()
        mock_pw.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_httpx_when_cookie_fetch_empty(self):
        with (
            patch("app.scrapers.fetcher.fetch_with_stored_cookies", new=AsyncMock(return_value=None)) as mock_cookies,
            patch("app.scrapers.fetcher.fetch_with_httpx", new=AsyncMock(return_value="httpx-html")) as mock_httpx,
            patch("app.scrapers.fetcher.fetch_with_playwright", new=AsyncMock(return_value="pw-html")) as mock_pw,
        ):
            result = await fetch_page("https://shop.example.com/p/1", stored_cookies={"sid": "abc"})

        assert result == "httpx-html"
        mock_cookies.assert_awaited_once()
        mock_httpx.assert_awaited_once()
        mock_pw.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_playwright_when_httpx_empty(self):
        with (
            patch("app.scrapers.fetcher.fetch_with_httpx", new=AsyncMock(return_value=None)) as mock_httpx,
            patch("app.scrapers.fetcher.fetch_with_playwright", new=AsyncMock(return_value="pw-html")) as mock_pw,
        ):
            result = await fetch_page("https://shop.example.com/p/1")

        assert result == "pw-html"
        mock_httpx.assert_awaited_once()
        mock_pw.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_httpx_for_playwright_required_domain(self):
        with (
            patch("app.scrapers.fetcher.fetch_with_httpx", new=AsyncMock(return_value="httpx-html")) as mock_httpx,
            patch("app.scrapers.fetcher.fetch_with_playwright", new=AsyncMock(return_value="pw-html")) as mock_pw,
        ):
            result = await fetch_page("https://www.target.com/p/123")

        assert result == "pw-html"
        mock_httpx.assert_not_awaited()
        mock_pw.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uses_playwright_with_cookies_for_js_heavy_domain(self):
        with (
            patch("app.scrapers.fetcher.fetch_with_stored_cookies", new=AsyncMock(return_value="cookie-html")) as mock_cookies,
            patch("app.scrapers.fetcher.fetch_with_httpx", new=AsyncMock(return_value="httpx-html")) as mock_httpx,
            patch("app.scrapers.fetcher.fetch_with_playwright", new=AsyncMock(return_value="pw-html")) as mock_pw,
        ):
            result = await fetch_page("https://www.freepeople.com/shop/item", stored_cookies={"sid": "abc"})

        assert result == "pw-html"
        mock_cookies.assert_not_awaited()
        mock_httpx.assert_not_awaited()
        mock_pw.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_cookie_httpx_when_playwright_blocked_for_js_heavy_domain(self):
        with (
            patch("app.scrapers.fetcher.fetch_with_stored_cookies", new=AsyncMock(return_value="cookie-html")) as mock_cookies,
            patch("app.scrapers.fetcher.fetch_with_httpx", new=AsyncMock(return_value="httpx-html")) as mock_httpx,
            patch("app.scrapers.fetcher.fetch_with_playwright", new=AsyncMock(side_effect=SiteBlockedError("blocked"))) as mock_pw,
        ):
            result = await fetch_page("https://www.freepeople.com/shop/item", stored_cookies={"sid": "abc"})

        assert result == "cookie-html"
        mock_pw.assert_awaited_once()
        mock_cookies.assert_awaited_once()
        mock_httpx.assert_not_awaited()
