"""Dev-only API endpoints. Only available when DEBUG=True."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.core.config import get_settings

router = APIRouter(prefix="/dev", tags=["dev"])

CASES_FILE = Path(__file__).resolve().parents[2] / "tests" / "cases.json"


class TestCaseExpect(BaseModel):
    price: str | None = None  # "ok" | "none" | null
    title: str | None = None
    image: str | None = None
    brand: str | None = None
    in_stock: str | None = None


class TestCaseIn(BaseModel):
    url: str
    label: str = ""
    fetch: str = "ok"
    expect: TestCaseExpect = TestCaseExpect()
    note: str = ""

    @field_validator("url")
    @classmethod
    def must_be_http(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.strip()


def _auto_label(url: str) -> str:
    """Generate a short label from the URL domain + first path segment."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.hostname or ""
        domain = re.sub(r"^www\.", "", domain)
        # Use first meaningful part of domain
        short_domain = domain.split(".")[0]
        # Use first non-empty path segment
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        slug = parts[0] if parts else "page"
        return f"{short_domain}/{slug}"
    except Exception:
        return "unknown/page"


@router.get("/test-cases")
async def list_test_cases() -> list[dict[str, Any]]:
    """List all test cases from cases.json."""
    _assert_debug_mode()
    if not CASES_FILE.exists():
        return []
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))


@router.post("/test-cases", status_code=201)
async def add_test_case(body: TestCaseIn) -> dict[str, Any]:
    """Append a new test case to cases.json."""
    _assert_debug_mode()

    cases: list[dict[str, Any]] = []
    if CASES_FILE.exists():
        cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))

    # Check for duplicate URL
    for c in cases:
        if c.get("url") == body.url:
            raise HTTPException(status_code=409, detail="URL already exists in test cases")

    label = body.label.strip() or _auto_label(body.url)

    entry: dict[str, Any] = {
        "url": body.url,
        "label": label,
        "fetch": body.fetch,
        "expect": {
            k: v for k, v in body.expect.model_dump().items() if v is not None
        },
        "note": body.note,
    }

    cases.append(entry)
    CASES_FILE.write_text(
        json.dumps(cases, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return entry


def _assert_debug_mode() -> None:
    if not get_settings().debug:
        raise HTTPException(status_code=403, detail="Dev endpoints require DEBUG=True")
