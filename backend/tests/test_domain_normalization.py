"""Tests for canonical domain handling across cookie and scraper paths."""

from app.scrapers.dispatcher import normalize_domain


def test_normalize_domain_strips_www_and_lowercases():
    assert normalize_domain("www.FreePeople.com") == "freepeople.com"


def test_normalize_domain_from_full_url():
    assert normalize_domain("https://www.freepeople.com/shop/item?id=1") == "freepeople.com"


def test_normalize_domain_keeps_plain_host():
    assert normalize_domain("freepeople.com") == "freepeople.com"
