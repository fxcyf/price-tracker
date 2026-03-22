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
