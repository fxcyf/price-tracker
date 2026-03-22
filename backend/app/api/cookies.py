from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import DB
from app.models.domain_rule import CookieStatus, DomainRule
from app.scrapers.curl_parser import parse_curl
from app.scrapers.dispatcher import normalize_domain, save_domain_cookies
from sqlalchemy import select

router = APIRouter(tags=["cookies"])


class CookieImportRequest(BaseModel):
    curl: str


class CookieStatusOut(BaseModel):
    domain: str
    status: str
    cookie_count: int | None
    updated_at: datetime | None


@router.put("/domains/{domain}/cookies", response_model=CookieStatusOut)
async def import_cookies(domain: str, body: CookieImportRequest, db: DB):
    """
    Import cookies for a bot-protected domain by pasting a curl command copied from DevTools.
    The cookies are stored and used automatically for all future fetches of this domain.
    """
    try:
        parsed = parse_curl(body.curl)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid curl command: {e}")

    if not parsed["cookies"]:
        raise HTTPException(status_code=400, detail="No cookies found in the curl command")

    # Allow the domain to come from the curl URL, but validate it matches the path param
    requested_domain = normalize_domain(domain)
    curl_domain = normalize_domain(parsed["domain"])
    if curl_domain and curl_domain != requested_domain:
        raise HTTPException(
            status_code=400,
            detail=f"curl URL domain ({curl_domain}) does not match path domain ({requested_domain})",
        )

    rule = await save_domain_cookies(db, requested_domain, parsed["cookies"])

    return CookieStatusOut(
        domain=rule.domain,
        status=rule.cookies_status,
        cookie_count=len(rule.cookies) if rule.cookies else None,
        updated_at=rule.cookies_updated_at,
    )


@router.get("/domains/{domain}/cookies", response_model=CookieStatusOut)
async def get_cookie_status(domain: str, db: DB):
    """
    Get the cookie status for a domain (valid / expired / none).
    Cookie values are never returned for security.
    """
    requested_domain = normalize_domain(domain)
    result = await db.execute(
        select(DomainRule).where(
            DomainRule.domain.in_([requested_domain, f"www.{requested_domain}"])
        )
    )
    rules = result.scalars().all()
    rule = next((r for r in rules if r.domain == requested_domain), rules[0] if rules else None)
    if not rule:
        return CookieStatusOut(domain=requested_domain, status=CookieStatus.NONE, cookie_count=None, updated_at=None)

    return CookieStatusOut(
        domain=rule.domain,
        status=rule.cookies_status,
        cookie_count=len(rule.cookies) if rule.cookies else None,
        updated_at=rule.cookies_updated_at,
    )
