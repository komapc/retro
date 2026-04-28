"""
Search endpoint logic — exposes web_search.py via async wrappers for /search and /search/health.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx

from tm import web_search as _ws

from .models import ProviderStatus, SearchHealthResponse, SearchRequest, SearchResponse, SearchResultItem

logger = logging.getLogger(__name__)


async def run_search(req: SearchRequest) -> SearchResponse:
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    if req.date_from:
        date_from = datetime.fromisoformat(req.date_from)
    if req.date_to:
        date_to = datetime.fromisoformat(req.date_to)

    results = await asyncio.to_thread(
        _ws.search_articles, req.query, req.limit, date_from, date_to
    )
    return SearchResponse(
        query=req.query,
        results=[
            SearchResultItem(
                title=r.title,
                url=r.url,
                snippet=r.snippet,
                source=r.source,
                published_date=r.published_date,
            )
            for r in results
        ],
        count=len(results),
    )


# ── Per-provider credit checks ────────────────────────────────────────────────

async def _check_serper() -> ProviderStatus:
    if not _ws.SERPERDEV_KEY:
        return ProviderStatus(configured=False, exhausted=False, status="not_configured")
    if _ws._SERPER_QUOTA_EXHAUSTED:
        return ProviderStatus(configured=True, exhausted=True, status="exhausted")
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                "https://google.serper.dev/account",
                headers={"X-API-KEY": _ws.SERPERDEV_KEY},
            )
        if not r.is_success:
            return ProviderStatus(configured=True, exhausted=False, status="error", error=f"HTTP {r.status_code}")
        credits = r.json().get("balance")
        return ProviderStatus(configured=True, exhausted=False, status="ok", credits=credits)
    except Exception as e:
        return ProviderStatus(configured=True, exhausted=False, status="error", error=str(e))


async def _check_serpapi() -> ProviderStatus:
    if not _ws.SERPAPI_KEY:
        return ProviderStatus(configured=False, exhausted=False, status="not_configured")
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"https://serpapi.com/account.json?api_key={_ws.SERPAPI_KEY}")
        if not r.is_success:
            return ProviderStatus(configured=True, exhausted=False, status="error", error=f"HTTP {r.status_code}")
        credits = r.json().get("searches_left")
        return ProviderStatus(configured=True, exhausted=False, status="ok", credits=credits)
    except Exception as e:
        return ProviderStatus(configured=True, exhausted=False, status="error", error=str(e))


async def _check_brave() -> ProviderStatus:
    if not _ws.BRAVE_API_KEY:
        return ProviderStatus(configured=False, exhausted=False, status="not_configured")
    if _ws._BRAVE_QUOTA_EXHAUSTED:
        return ProviderStatus(configured=True, exhausted=True, status="exhausted")
    # Brave has no public credit-check API; report key presence + in-process flag only
    return ProviderStatus(configured=True, exhausted=False, status="ok")


async def _check_brightdata() -> ProviderStatus:
    if not _ws.BRIGHTDATA_API_KEY:
        return ProviderStatus(configured=False, exhausted=False, status="not_configured")
    if _ws._BRIGHTDATA_QUOTA_EXHAUSTED:
        return ProviderStatus(configured=True, exhausted=True, status="exhausted")
    return ProviderStatus(configured=True, exhausted=False, status="ok")


async def _check_nimbleway() -> ProviderStatus:
    if not _ws.NIMBLEWAY_API_KEY:
        return ProviderStatus(configured=False, exhausted=False, status="not_configured")
    if _ws._NIMBLEWAY_QUOTA_EXHAUSTED:
        return ProviderStatus(configured=True, exhausted=True, status="exhausted")
    return ProviderStatus(configured=True, exhausted=False, status="ok")


async def _check_scrapingbee() -> ProviderStatus:
    if not _ws.SCRAPINGBEE_API_KEY:
        return ProviderStatus(configured=False, exhausted=False, status="not_configured")
    if _ws._SCRAPINGBEE_QUOTA_EXHAUSTED:
        return ProviderStatus(configured=True, exhausted=True, status="exhausted")
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                "https://app.scrapingbee.com/api/v1/usage",
                params={"api_key": _ws.SCRAPINGBEE_API_KEY},
            )
        if not r.is_success:
            return ProviderStatus(configured=True, exhausted=False, status="error", error=f"HTTP {r.status_code}")
        data = r.json()
        max_c = data.get("max_api_credit")
        used_c = data.get("used_api_credit")
        credits = (max_c - used_c) if (max_c is not None and used_c is not None) else None
        return ProviderStatus(configured=True, exhausted=False, status="ok", credits=credits)
    except Exception as e:
        return ProviderStatus(configured=True, exhausted=False, status="error", error=str(e))


async def run_search_health() -> SearchHealthResponse:
    checks = await asyncio.gather(
        _check_serper(),
        _check_serpapi(),
        _check_brave(),
        _check_brightdata(),
        _check_nimbleway(),
        _check_scrapingbee(),
    )
    providers: dict[str, ProviderStatus] = {
        "serpapi":    checks[1],
        "serper":     checks[0],
        "brave":      checks[2],
        "brightdata": checks[3],
        "nimbleway":  checks[4],
        "scrapingbee":checks[5],
        "ddg": ProviderStatus(
            configured=True, exhausted=False, status="ok",
        ),
    }

    # Usable = configured + not exhausted + status ok, excluding DDG (blocked on EC2)
    usable = sum(
        1 for k, p in providers.items()
        if k != "ddg" and p.configured and not p.exhausted and p.status == "ok"
    )
    overall = "ok" if usable >= 2 else ("degraded" if usable == 1 else "down")

    return SearchHealthResponse(providers=providers, overall=overall, usable_count=usable)
