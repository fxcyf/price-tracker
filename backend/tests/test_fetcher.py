"""
Tests for app.scrapers.fetcher.preprocess_html.
"""

from app.scrapers.fetcher import preprocess_html


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
