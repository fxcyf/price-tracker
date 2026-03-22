"""Shared pytest fixtures for scraper tests."""

from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Reusable HTML builders — inline HTML snippets for focused unit tests
# ---------------------------------------------------------------------------

def make_html(head: str = "", body: str = "") -> str:
    return f"<!DOCTYPE html><html><head>{head}</head><body>{body}</body></html>"


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run live network scraper regression tests",
    )
    parser.addoption(
        "--live-curl-file",
        action="store",
        default="",
        help="path to a curl command file used by live cookie regression tests",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "live: marks tests that hit real websites")
    config.addinivalue_line("markers", "slow: marks tests that are slow to run")
    config.addinivalue_line(
        "markers",
        "live_cookie: marks tests that validate cookie-backed live scraping",
    )


def pytest_collection_modifyitems(config, items):
    run_live = config.getoption("--run-live")
    live_curl_file = config.getoption("--live-curl-file")
    skip_live = pytest.mark.skip(reason="need --run-live option to run")
    skip_cookie_live = pytest.mark.skip(
        reason="need --live-curl-file to run cookie live regression tests",
    )
    for item in items:
        if "live" in item.keywords and not run_live:
            item.add_marker(skip_live)
        if "live_cookie" in item.keywords and not live_curl_file:
            item.add_marker(skip_cookie_live)
