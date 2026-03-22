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


def pytest_configure(config):
    config.addinivalue_line("markers", "live: marks tests that hit real websites")
    config.addinivalue_line("markers", "slow: marks tests that are slow to run")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="need --run-live option to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
