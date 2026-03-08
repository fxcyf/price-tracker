import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BROWSER_PROFILE_DIR = Path.home() / ".price-tracker-browser-profile"

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


async def fetch_with_stored_cookies(url: str, cookies: dict) -> str | None:
    """
    Attempt a fast httpx fetch using user-imported cookies (e.g. from a real browser).
    Returns HTML on success, None if cookies appear expired or request failed.
    Raises CookiesExpiredError when the response signals the cookies are no longer valid.
    """
    domain = (urlparse(url).hostname or "").removeprefix("www.")
    try:
        async with httpx.AsyncClient(
            cookies=cookies,
            headers=HEADERS,
            follow_redirects=True,
            timeout=15,
        ) as client:
            response = await client.get(url)
            html = response.text

            if response.status_code in (403, 401) or _is_blocked(html):
                raise CookiesExpiredError(domain)

            if _looks_complete(html):
                logger.debug("fetch_with_stored_cookies succeeded for %s", url)
                return html

            return None
    except CookiesExpiredError:
        raise
    except Exception as exc:
        logger.debug("fetch_with_stored_cookies failed for %s: %s", url, exc)
        return None


async def fetch_with_httpx(url: str) -> str | None:
    """Fast anonymous fetch using httpx."""
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            if _looks_complete(html):
                return html
            logger.debug("httpx fetch incomplete for %s, will try Playwright", url)
            return None
    except Exception as exc:
        logger.debug("httpx fetch failed for %s: %s", url, exc)
        return None


async def fetch_with_playwright(url: str) -> str:
    """Full browser fetch using a persistent Playwright context with stealth."""
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    stealth = Stealth(
        navigator_user_agent_override=HEADERS["User-Agent"],
        navigator_platform_override="Linux x86_64",
    )

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(BROWSER_PROFILE_DIR),
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
        await stealth.apply_stealth_async(context)
        page = await context.new_page()
        try:
            origin = f"{urlparse(url).scheme}://{urlparse(url).hostname}"
            try:
                await page.goto(origin, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2500)
            except Exception:
                pass
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            html = await page.content()
        finally:
            await context.close()

    if _is_blocked(html):
        raise SiteBlockedError(
            f"Site blocked automated access for URL: {url}. "
            "Import cookies from your browser to enable tracking for this site."
        )
    return html


async def fetch_page(url: str, stored_cookies: dict | None = None) -> str:
    """
    Fetch a page's HTML. Priority order:
      1. Stored user cookies (httpx) — fastest, works for PerimeterX-protected sites
      2. Anonymous httpx — fast, works for most sites
      3. Playwright with persistent profile — handles JS rendering and light bot protection
    """
    domain = (urlparse(url).hostname or "").removeprefix("www.")

    # Layer 0: user-imported cookies (bypasses PerimeterX, Cloudflare with session)
    if stored_cookies:
        html = await fetch_with_stored_cookies(url, stored_cookies)
        # CookiesExpiredError propagates up — caller handles notification
        if html:
            return html

    # Layer 1: anonymous httpx
    html = await fetch_with_httpx(url)
    if html:
        return html

    # Layer 2: Playwright with persistent profile
    logger.info("Falling back to Playwright for %s", url)
    return await fetch_with_playwright(url)


def preprocess_html(html: str, max_chars: int = 8000) -> str:
    """Strip noise from HTML and truncate for LLM consumption."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:max_chars]
