from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BROWSER_PROFILE_DIR = Path.home() / ".price-tracker-browser-profile"
FETCH_HTTP_TIMEOUT_SECONDS = settings.fetch_http_timeout_seconds
FETCH_PLAYWRIGHT_ORIGIN_TIMEOUT_MS = settings.fetch_playwright_origin_timeout_ms
FETCH_PLAYWRIGHT_NAV_TIMEOUT_MS = settings.fetch_playwright_nav_timeout_ms
FETCH_PLAYWRIGHT_SETTLE_TIMEOUT_MS = settings.fetch_playwright_settle_timeout_ms
FETCH_RETRY_ATTEMPTS = settings.fetch_retry_attempts
FETCH_RETRY_BACKOFF_SECONDS = settings.fetch_retry_backoff_seconds

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "sec-ch-ua": '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
}

# Sites that serve a React/Next.js shell via httpx (looks "complete" but has no price).
# For these, skip httpx and go straight to Playwright.
PLAYWRIGHT_REQUIRED_DOMAINS = {
    "target.com",
    "bestbuy.com",
    # httpx gets a 1MB JS bundle where all product/price data lives inside
    # <script id="__NEXT_DATA__"> — preprocess_html strips all scripts, leaving
    # the LLM with ~4KB of nav text and no price. Playwright renders the full
    # React DOM so the price is visible as actual text.
    "jcrew.com",
    # JS-heavy storefronts that frequently need rendered DOM.
    "freepeople.com",
    "urbanoutfitters.com",
    "aritzia.com",
    # React SPA: httpx returns the JS bundle shell; price lives in rendered DOM.
    "homedepot.com",
    # Shopify-based storefront; product data is JS-injected.
    "maisonkitsune.com",
    # Magento Venia PWA: httpx gets "JavaScript is disabled" shell page.
    "tntsupermarket.us",
}

BLOCKED_SIGNALS = [
    "robot check",
    "access denied",
    "403 forbidden",
    "you don't have permission",
    "reference #18",               # Akamai error ID pattern (specific prefix avoids false positives)
    "edgesuite.net",               # Akamai CDN domain
    "distilnetworks",              # Distil bot detection
    "datadome",                    # DataDome bot detection
    "px-captcha",                  # PerimeterX dedicated block page element
    "enable javascript and cookies",  # Cloudflare JS challenge page
]


class SiteBlockedError(Exception):
    """Raised when the site actively blocks our request and no user cookies are stored."""
    pass


class CookiesExpiredError(Exception):
    """Raised when stored user cookies are detected as expired."""
    def __init__(self, domain: str):
        self.domain = domain
        super().__init__(
            f"Stored cookies for {domain} have expired. "
            "Please visit the site in your browser and import new cookies."
        )


def _is_blocked(html: str) -> bool:
    """True only when the page content clearly signals an active bot wall."""
    lower = html.lower()
    return any(kw in lower for kw in BLOCKED_SIGNALS)


def _looks_complete(html: str) -> bool:
    """True when the page looks like real product content (not blocked, not suspiciously tiny)."""
    return not _is_blocked(html) and len(html) >= 5000


def _is_retryable_httpx_exception(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        return 500 <= exc.response.status_code < 600
    return False


def _should_retry(attempt: int) -> bool:
    return attempt < FETCH_RETRY_ATTEMPTS


async def _sleep_retry_delay(attempt: int) -> None:
    delay = FETCH_RETRY_BACKOFF_SECONDS * (2 ** attempt)
    await asyncio.sleep(delay)


async def fetch_with_curl_cffi(url: str, cookies: dict) -> str | None:
    """
    Cookie-backed fetch using curl_cffi Chrome TLS impersonation.

    PerimeterX and similar systems cryptographically bind their session cookies
    (_px3, etc.) to the TLS fingerprint of the originating browser. httpx produces
    a different JA3/JA4 fingerprint, so cookie replay via httpx is rejected even
    when the cookies are valid. curl_cffi with ``impersonate="chrome"`` reproduces
    Chrome's exact TLS/HTTP2 handshake, making the fingerprint match and allowing
    the server-side cookie validation to pass.

    Returns HTML on success, None if curl_cffi is unavailable or the request failed.
    Raises CookiesExpiredError when the response signals the cookies are invalid.
    """
    try:
        from curl_cffi.requests import AsyncSession as CurlSession
    except ImportError:
        logger.debug("curl_cffi not available; skipping TLS-impersonation fetch for %s", url)
        return None

    domain = (urlparse(url).hostname or "").removeprefix("www.")
    for attempt in range(FETCH_RETRY_ATTEMPTS + 1):
        try:
            async with CurlSession(impersonate="chrome") as session:
                response = await session.get(
                    url,
                    headers=HEADERS,
                    cookies=cookies,
                    allow_redirects=True,
                    timeout=FETCH_HTTP_TIMEOUT_SECONDS,
                )
                html = response.text

                if response.status_code in (403, 401) or _is_blocked(html):
                    raise CookiesExpiredError(domain)

                if response.status_code < 400:
                    logger.debug(
                        "curl_cffi fetch succeeded for %s (len=%d)", url, len(html)
                    )
                    return html

                return None
        except CookiesExpiredError:
            raise
        except Exception as exc:
            logger.debug(
                "curl_cffi fetch failed for %s (attempt %s/%s): %s",
                url,
                attempt + 1,
                FETCH_RETRY_ATTEMPTS + 1,
                exc,
            )
            if _should_retry(attempt):
                await _sleep_retry_delay(attempt)
                continue
            return None
    return None


async def fetch_with_stored_cookies(url: str, cookies: dict) -> str | None:
    """
    Attempt a fast httpx fetch using user-imported cookies (e.g. from a real browser).
    Returns HTML on success, None if cookies appear expired or request failed.
    Raises CookiesExpiredError when the response signals the cookies are no longer valid.
    """
    domain = (urlparse(url).hostname or "").removeprefix("www.")
    for attempt in range(FETCH_RETRY_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(
                cookies=cookies,
                headers=HEADERS,
                follow_redirects=True,
                timeout=FETCH_HTTP_TIMEOUT_SECONDS,
            ) as client:
                response = await client.get(url)
                html = response.text

                if response.status_code in (403, 401) or _is_blocked(html):
                    raise CookiesExpiredError(domain)

                # For user-imported cookies, a successful non-blocked response is already
                # valuable, even if HTML is shorter than our generic anonymous threshold.
                # Returning it avoids unnecessary Playwright fallback that can hit bot walls.
                if response.status_code < 400:
                    if not _looks_complete(html):
                        logger.debug(
                            "fetch_with_stored_cookies got short but usable HTML for %s (len=%d)",
                            url,
                            len(html),
                        )
                    else:
                        logger.debug("fetch_with_stored_cookies succeeded for %s", url)
                    return html

                return None
        except CookiesExpiredError:
            raise
        except Exception as exc:
            retryable = _is_retryable_httpx_exception(exc)
            logger.debug(
                "fetch_with_stored_cookies failed for %s (attempt %s/%s): %s",
                url,
                attempt + 1,
                FETCH_RETRY_ATTEMPTS + 1,
                exc,
            )
            if retryable and _should_retry(attempt):
                await _sleep_retry_delay(attempt)
                continue
            return None
    return None


async def fetch_with_httpx(url: str) -> str | None:
    """Fast anonymous fetch using httpx."""
    for attempt in range(FETCH_RETRY_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                timeout=FETCH_HTTP_TIMEOUT_SECONDS,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
                if _looks_complete(html):
                    return html
                logger.debug("httpx fetch incomplete for %s, will try Playwright", url)
                return None
        except Exception as exc:
            retryable = _is_retryable_httpx_exception(exc)
            logger.debug(
                "httpx fetch failed for %s (attempt %s/%s): %s",
                url,
                attempt + 1,
                FETCH_RETRY_ATTEMPTS + 1,
                exc,
            )
            if retryable and _should_retry(attempt):
                await _sleep_retry_delay(attempt)
                continue
            return None
    return None


def _cookies_for_playwright(url: str, cookies: dict | None) -> list[dict]:
    if not cookies:
        return []
    hostname = urlparse(url).hostname or ""
    normalized = hostname.removeprefix("www.")
    cookie_domain = f".{normalized}" if normalized else hostname
    return [
        {
            "name": name,
            "value": value,
            "domain": cookie_domain,
            "path": "/",
        }
        for name, value in cookies.items()
    ]


async def fetch_with_playwright(url: str, stored_cookies: dict | None = None) -> str:
    """Full browser fetch using a persistent Playwright context with stealth."""
    import os
    from playwright.async_api import async_playwright
    try:
        from playwright_stealth import Stealth
    except ImportError:  # pragma: no cover - depends on runtime environment
        Stealth = None

    # Each process gets its own profile dir to avoid lock contention between
    # concurrent Celery ForkPoolWorkers sharing the same filesystem path.
    profile_dir = BROWSER_PROFILE_DIR / str(os.getpid())
    profile_dir.mkdir(parents=True, exist_ok=True)
    stealth = None
    if Stealth is not None:
        stealth = Stealth(
            navigator_user_agent_override=HEADERS["User-Agent"],
            navigator_platform_override="Linux x86_64",
        )
    else:
        logger.warning(
            "playwright_stealth is not installed; continuing without stealth for %s",
            url,
        )

    for attempt in range(FETCH_RETRY_ATTEMPTS + 1):
        try:
            async with async_playwright() as p:
                context = await p.chromium.launch_persistent_context(
                    str(profile_dir),
                    headless=True,
                    user_agent=HEADERS["User-Agent"],
                    locale="en-US",
                    viewport={"width": 1280, "height": 800},
                    extra_http_headers={
                        "sec-ch-ua": HEADERS["sec-ch-ua"],
                        "sec-ch-ua-mobile": HEADERS["sec-ch-ua-mobile"],
                        "sec-ch-ua-platform": HEADERS["sec-ch-ua-platform"],
                        "dnt": "1",
                    },
                    args=["--disable-blink-features=AutomationControlled"],
                )
                playwright_cookies = _cookies_for_playwright(url, stored_cookies)
                if playwright_cookies:
                    await context.add_cookies(playwright_cookies)
                if stealth is not None:
                    await stealth.apply_stealth_async(context)
                page = await context.new_page()
                try:
                    origin = f"{urlparse(url).scheme}://{urlparse(url).hostname}"
                    try:
                        await page.goto(origin, wait_until="domcontentloaded", timeout=FETCH_PLAYWRIGHT_ORIGIN_TIMEOUT_MS)
                        await page.wait_for_timeout(min(2500, FETCH_PLAYWRIGHT_SETTLE_TIMEOUT_MS))
                    except Exception:
                        pass
                    await page.goto(url, wait_until="domcontentloaded", timeout=FETCH_PLAYWRIGHT_NAV_TIMEOUT_MS)
                    await page.wait_for_timeout(FETCH_PLAYWRIGHT_SETTLE_TIMEOUT_MS)
                    html = await page.content()
                finally:
                    await context.close()

            if _is_blocked(html):
                raise SiteBlockedError(
                    f"Site blocked automated access for URL: {url}. "
                    "Import cookies from your browser to enable tracking for this site."
                )
            return html
        except SiteBlockedError:
            raise
        except Exception as exc:
            logger.debug(
                "Playwright fetch failed for %s (attempt %s/%s): %s",
                url,
                attempt + 1,
                FETCH_RETRY_ATTEMPTS + 1,
                exc,
            )
            if _should_retry(attempt):
                await _sleep_retry_delay(attempt)
                continue
            raise
    raise RuntimeError(f"Playwright fetch failed after retries for {url}")


async def fetch_page(url: str, stored_cookies: dict | None = None) -> str:
    """
    Fetch a page's HTML. Priority order:
      1. curl_cffi + cookies — Chrome TLS impersonation, bypasses PerimeterX/Cloudflare
         cookie validation that rejects httpx's different TLS fingerprint
      2. Playwright + cookies — full browser render with session cookies injected
      3. Anonymous httpx — fast, works for most non-SPA sites
      4. Playwright (anonymous) — handles JS rendering and light bot protection
    """
    domain = (urlparse(url).hostname or "").removeprefix("www.")
    needs_playwright = any(domain == d or domain.endswith(f".{d}") for d in PLAYWRIGHT_REQUIRED_DOMAINS)

    # Layer 0: user cookies via curl_cffi (Chrome TLS impersonation).
    # This is the most reliable path for PerimeterX/Cloudflare-protected sites:
    # the JA3/JA4 fingerprint matches Chrome, so the server-side cookie validation passes.
    # CookiesExpiredError propagates up — caller handles notification.
    if stored_cookies:
        html = await fetch_with_curl_cffi(url, stored_cookies)
        if html:
            return html
        # curl_cffi unavailable (returned None without raising) — fall through.
        # If cookies were expired/blocked, CookiesExpiredError was already raised above.

    # Layer 0b: JS-heavy domains with imported cookies — browser render with session injected.
    # Used as a fallback when curl_cffi is not installed.
    if stored_cookies and needs_playwright:
        logger.info("curl_cffi unavailable; using Playwright with stored cookies for %s", url)
        try:
            return await fetch_with_playwright(url, stored_cookies=stored_cookies)
        except SiteBlockedError:
            # Some anti-bot stacks dislike headless execution even with valid cookies.
            # Retry once with cookie-backed httpx before surfacing a hard block.
            logger.info(
                "Playwright+cookies blocked for %s, retrying with cookie-httpx",
                url,
            )
            html = await fetch_with_stored_cookies(url, stored_cookies)
            if html:
                return html
            raise

    # Layer 0c: non-JS-heavy sites with cookies but no curl_cffi — plain httpx fallback.
    if stored_cookies and not needs_playwright:
        html = await fetch_with_stored_cookies(url, stored_cookies)
        if html:
            return html

    # Layer 1: anonymous httpx — skipped for known JS-heavy SPAs
    if not needs_playwright:
        html = await fetch_with_httpx(url)
        if html:
            return html

    # Layer 2: Playwright with persistent profile
    logger.info("Falling back to Playwright for %s", url)
    return await fetch_with_playwright(url)


def preprocess_html(html: str, max_chars: int = 12000) -> str:
    """Strip noise from HTML and truncate for LLM consumption."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:max_chars]
