"""
Multi-provider news search with fallback chain.
Python equivalent of daatan's webSearch.ts utility.

Fallback order:
  1. Serper.dev /news endpoint  (SERPERDEV_KEY)
  2. Brave News Search           (BRAVE_API_KEY)
  3. DuckDuckGo Lite             (free, no key)

Usage:
    from tm.web_search import search_articles

    results = search_articles(
        "Gaza ceasefire negotiations site:timesofisrael.com",
        limit=5,
        date_from=datetime(2024, 1, 1),
        date_to=datetime(2024, 1, 14),
    )
    for r in results:
        print(r.url, r.title)
"""

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import httpx
from ddgs import DDGS

SERPERDEV_KEY: Optional[str] = os.environ.get("SERPERDEV_KEY")
BRAVE_API_KEY: Optional[str] = os.environ.get("BRAVE_API_KEY")


def _running_on_ec2() -> bool:
    """Detect AWS EC2 via instance metadata endpoint (fast timeout)."""
    try:
        import httpx as _httpx
        r = _httpx.get("http://169.254.169.254/latest/meta-data/", timeout=0.3)
        return r.status_code == 200
    except Exception:
        return False

_DDG_LAST_CALL: float = 0.0
DDG_MIN_INTERVAL = 2.0

_BRAVE_QUOTA_EXHAUSTED: bool = False


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = ""
    published_date: str = ""


# ──────────────────────────────────────────────
# Provider: Serper.dev /news
# ──────────────────────────────────────────────

def _search_serper_news(
    query: str,
    limit: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[SearchResult]:
    if not SERPERDEV_KEY:
        raise RuntimeError("SERPERDEV_KEY not set")

    body: dict = {"q": query, "num": limit}
    if date_from and date_to:
        # Serper tbs date range: cdr:1,cd_min:M/D/YYYY,cd_max:M/D/YYYY
        def _fmt(dt: datetime) -> str:
            return f"{dt.month}/{dt.day}/{dt.year}"
        body["tbs"] = f"cdr:1,cd_min:{_fmt(date_from)},cd_max:{_fmt(date_to)}"

    r = httpx.post(
        "https://google.serper.dev/news",
        json=body,
        headers={"X-API-KEY": SERPERDEV_KEY, "Content-Type": "application/json"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    items = data.get("news", [])

    return [
        SearchResult(
            title=item.get("title", ""),
            url=item.get("link", ""),
            snippet=item.get("snippet", ""),
            source=_extract_domain(item.get("link", "")),
            published_date=item.get("date", ""),
        )
        for item in items[:limit]
        if item.get("link")
    ]


# ──────────────────────────────────────────────
# Provider: Brave News Search
# ──────────────────────────────────────────────

def _search_brave_news(
    query: str,
    limit: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[SearchResult]:
    global _BRAVE_QUOTA_EXHAUSTED
    if not BRAVE_API_KEY:
        raise RuntimeError("BRAVE_API_KEY not set")

    params: dict = {
        "q": query,
        "count": min(limit, 20),
        "search_lang": "en",
        "result_filter": "news",
    }
    # Brave supports freshness but not arbitrary date ranges; skip date filter here
    # (caller should include dates in the query string instead)

    r = httpx.get(
        "https://api.search.brave.com/res/v1/news/search",
        params=params,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": BRAVE_API_KEY,
        },
        timeout=10,
    )
    if r.status_code == 402:
        _BRAVE_QUOTA_EXHAUSTED = True
        raise RuntimeError("Brave quota exhausted (402)")
    r.raise_for_status()

    items = r.json().get("results", [])
    return [
        SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("description", ""),
            source=item.get("meta_url", {}).get("hostname", _extract_domain(item.get("url", ""))),
            published_date=item.get("age", ""),
        )
        for item in items[:limit]
        if item.get("url")
    ]


# ──────────────────────────────────────────────
# Provider: DuckDuckGo Lite (free fallback)
# ──────────────────────────────────────────────

def _search_ddg_news(query: str, limit: int) -> List[SearchResult]:
    global _DDG_LAST_CALL
    elapsed = time.time() - _DDG_LAST_CALL
    if elapsed < DDG_MIN_INTERVAL:
        time.sleep(DDG_MIN_INTERVAL - elapsed)

    results = []
    with DDGS() as d:
        for item in d.text(query, max_results=limit):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("href", ""),
                    snippet=item.get("body", ""),
                    source=_extract_domain(item.get("href", "")),
                )
            )
    _DDG_LAST_CALL = time.time()
    return results[:limit]


# ──────────────────────────────────────────────
# Public API — tries providers in order
# ──────────────────────────────────────────────

def search_articles(
    query: str,
    limit: int = 10,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[SearchResult]:
    """
    Search for news articles matching *query*, returning up to *limit* results.
    Tries providers in order: Serper.dev → Brave → DuckDuckGo.
    Providers without an API key are skipped.

    Args:
        query:     Search string. Include `site:domain.com` to restrict to a source.
        limit:     Max results to return.
        date_from: Optional start of date window.
        date_to:   Optional end of date window.

    Returns:
        List of SearchResult(title, url, snippet, source, published_date).
    """
    # 1. Serper.dev news
    if SERPERDEV_KEY:
        try:
            results = _search_serper_news(query, limit, date_from, date_to)
            if results:
                return results
        except Exception as e:
            pass  # fall through to next provider

    # 2. Brave News
    if BRAVE_API_KEY and not _BRAVE_QUOTA_EXHAUSTED:
        try:
            results = _search_brave_news(query, limit, date_from, date_to)
            if results:
                return results
        except Exception:
            pass

    # 3. DuckDuckGo (free, no key) — skip on EC2: AWS IPs are blocked by DDG/Yahoo
    if not _running_on_ec2():
        try:
            return _search_ddg_news(query, limit)
        except Exception:
            pass

    return []


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    try:
        return re.sub(r"^www\.", "", __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url).netloc)
    except Exception:
        return ""
