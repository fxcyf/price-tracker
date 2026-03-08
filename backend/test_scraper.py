"""
Scraper test — four modes:

1. Fixture mode (default): tests extraction layers against local HTML files
   python test_scraper.py

2. Live mode: fetches a real URL and runs all layers
   python test_scraper.py --live https://www.madewell.com/...

3. Live-with-cookies (from file): paste the curl into a file, then pass the path
   python test_scraper.py --live-curl curl.txt

4. Live-with-cookies (from stdin): pipe the curl in, or just run and paste + Ctrl-D
   python test_scraper.py --live-curl -
   pbpaste | python test_scraper.py --live-curl -
"""

import asyncio
import sys
from pathlib import Path

from app.scrapers.curl_parser import parse_curl
from app.scrapers.extractors.opengraph import extract_opengraph
from app.scrapers.extractors.rules import extract_by_rules, extract_by_learned_rule
from app.scrapers.fetcher import preprocess_html, fetch_page, CookiesExpiredError
from app.scrapers.schemas import ProductData

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


def print_result(label: str, data: ProductData) -> None:
    status = "COMPLETE" if data.is_complete() else "incomplete"
    print(f"  [{label}] ({status})")
    print(f"    title    : {data.title}")
    print(f"    price    : {data.price} {data.currency}")
    print(f"    image    : {data.image_url}")
    print(f"    category : {data.category}")
    print(f"    platform : {data.platform}")


def run_fixture_test(fixture_name: str, url: str, learned_selectors: dict | None = None) -> None:
    html = (FIXTURES / fixture_name).read_text()
    print(f"\n{'='*60}")
    print(f"Fixture : {fixture_name}")
    print(f"URL     : {url}")
    print("="*60)

    run_test(html, url, learned_selectors)


async def run_real_world_test(url: str) -> None:
    print(f"\n{'='*60}")
    print(f"URL     : {url}")
    html = await fetch_page(url)
    if not html or html == "":
        print("Failed to fetch HTML")
        return

    print("HTML fetched successfully")
    run_test(html, url)


async def run_curl_test(curl_string: str) -> None:
    """Parse a curl command from DevTools and test scraping with those cookies."""
    print(f"\n{'='*60}")
    print("Mode: live-with-cookies (curl import)")
    print("="*60)

    try:
        parsed = parse_curl(curl_string)
    except ValueError as e:
        print(f"  [ERROR] Failed to parse curl: {e}")
        return

    url = parsed["url"]
    domain = parsed["domain"]
    cookies = parsed["cookies"]

    print(f"URL     : {url}")
    print(f"Domain  : {domain}")
    print(f"Cookies : {len(cookies)} found — {list(cookies.keys())}")

    if not cookies:
        print("  [WARN] No cookies found in curl command — will fetch without cookies")

    print("\nFetching page...")
    try:
        html = await fetch_page(url, stored_cookies=cookies or None)
    except CookiesExpiredError as e:
        print(f"  [BLOCKED] Cookies appear expired: {e}")
        return
    except Exception as e:
        print(f"  [ERROR] Fetch failed: {e}")
        return

    print(f"HTML fetched successfully ({len(html):,} chars)")
    run_test(html, url)


def run_test(html: str, url: str, learned_selectors: dict | None = None) -> None:
    og = extract_opengraph(html, url)
    print_result("Layer 1: OpenGraph/JSON-LD", og)

    rules = extract_by_rules(html, url)
    print_result("Layer 2a: Platform rules", rules)

    merged = og.merge(rules)

    if learned_selectors:
        learned = extract_by_learned_rule(
            html, url,
            price_selector=learned_selectors.get("price"),
            title_selector=learned_selectors.get("title"),
            image_selector=learned_selectors.get("image"),
        )
        print_result("Layer 2b: Learned rules", learned)
        merged = merged.merge(learned)

    print_result(">> Final merged result", merged)

    if not merged.is_complete():
        print("\n  [Layer 3 would trigger] Preprocessed text snippet:")
        snippet = preprocess_html(html)
        print("  " + snippet[:300].replace("\n", "\n  ") + "...")



if __name__ == "__main__":
    # Live mode: python test_scraper.py --live <url>
    if len(sys.argv) >= 3 and sys.argv[1] == "--live":
        url = sys.argv[2]
        print(f"\n[Live mode] Fetching: {url}")
        asyncio.run(run_real_world_test(url))
        sys.exit(0)

    # Cookie mode: read curl from a file path or stdin ("-")
    #   python test_scraper.py --live-curl curl.txt
    #   python test_scraper.py --live-curl -     (paste + Ctrl-D)
    #   cat curl.txt | python test_scraper.py --live-curl -
    if len(sys.argv) >= 2 and sys.argv[1] == "--live-curl":
        source = sys.argv[2] if len(sys.argv) >= 3 else "-"
        if source == "-":
            print("Paste your curl command below, then press Ctrl-D (Linux) or Ctrl-Z+Enter (Windows):")
            curl_string = sys.stdin.read()
        else:
            curl_string = Path(source).read_text()
        asyncio.run(run_curl_test(curl_string))
        sys.exit(0)

    # Fixture mode (default)
    run_fixture_test(
        "amazon_product.html",
        "https://www.amazon.com/dp/B0CHWRXH8B",
    )
    run_fixture_test(
        "generic_product.html",
        "https://www.somestore.com/products/sony-xm5",
    )
    run_fixture_test(
        "no_og_product.html",
        "https://www.unknownstore.com/products/x900",
        learned_selectors={
            "price": ".sale-price",
            "title": "h1.product-name",
            "image": "img.product-image",
        },
    )
    run_fixture_test(
        "no_og_product.html",
        "https://www.unknownstore.com/products/x900",
    )
