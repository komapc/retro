"""
Multi-provider news search with fallback chain.
Python equivalent of daatan's webSearch.ts utility.

Fallback order:
  1. SerpAPI (serpapi.com)          SERPAPI_API_KEY
  2. Serper.dev /news endpoint      SERPER_API_KEY
  3. Brave News Search              BRAVE_API_KEY
  4. BrightData SERP API            BRIGHTDATA_API_KEY
  5. Nimbleway SERP API             NIMBLEWAY_API_KEY
  6. ScrapingBee Google Search      SCRAPINGBEE_API_KEY
  7. DuckDuckGo Lite                (free, no key — skipped on EC2)

All keys are loaded from the environment first, then from AWS Secrets Manager
(openclaw/* namespace) as a fallback. See _secret().

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

import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlencode

import httpx
from ddgs import DDGS

logger = logging.getLogger(__name__)

# Thread-local: stores the provider name that served the last search_articles()
# call in this thread. Read via get_last_search_provider() after the call returns.
_provider_local = threading.local()


def get_last_search_provider() -> str:
    """Return the provider that served the most recent search_articles() call in this thread."""
    return getattr(_provider_local, "name", "none")


def _secret(env_var: str, secret_name: str) -> Optional[str]:
    """Return env var if set, otherwise fetch from AWS Secrets Manager."""
    val = os.environ.get(env_var)
    if val:
        return val
    try:
        import boto3
        client = boto3.client("secretsmanager", region_name="eu-central-1")
        val = client.get_secret_value(SecretId=secret_name)["SecretString"].strip()
        logger.info("Loaded %s from Secrets Manager", secret_name)
        return val
    except Exception as e:
        logger.debug("Could not load %s from Secrets Manager: %s", secret_name, e)
        return None


SERPAPI_API_KEY: Optional[str] = _secret("SERPAPI_API_KEY", "openclaw/serpapi-key")
SERPER_API_KEY: Optional[str] = _secret("SERPER_API_KEY", "openclaw/serperdev-key")
BRAVE_API_KEY: Optional[str] = _secret("BRAVE_API_KEY", "openclaw/brave-api-key")
BRIGHTDATA_API_KEY: Optional[str] = _secret("BRIGHTDATA_API_KEY", "openclaw/brightdata-api-key")
NIMBLEWAY_API_KEY: Optional[str] = _secret("NIMBLEWAY_API_KEY", "openclaw/nimbleway-api-key")
SCRAPINGBEE_API_KEY: Optional[str] = _secret("SCRAPINGBEE_API_KEY", "openclaw/scrapingbee-api-key")

_KEY_LOADED_AT: float = time.time()
_KEY_MAX_AGE_SECONDS: float = 86400.0  # 24h


def _refresh_keys_if_stale() -> None:
    """Re-fetch all search API keys from Secrets Manager if >24h old.

    Keys are loaded once at module import. Long-running processes (the batch
    pipeline can run for days) would use stale keys after rotation. This
    function is called at the top of search_articles() to catch that case.
    """
    global SERPAPI_API_KEY, SERPER_API_KEY, BRAVE_API_KEY
    global BRIGHTDATA_API_KEY, NIMBLEWAY_API_KEY, SCRAPINGBEE_API_KEY
    global _KEY_LOADED_AT
    if time.time() - _KEY_LOADED_AT < _KEY_MAX_AGE_SECONDS:
        return
    logger.info("Refreshing search API keys from Secrets Manager (>24h since last fetch)")
    SERPAPI_API_KEY = _secret("SERPAPI_API_KEY", "openclaw/serpapi-key")
    SERPER_API_KEY = _secret("SERPER_API_KEY", "openclaw/serperdev-key")
    BRAVE_API_KEY = _secret("BRAVE_API_KEY", "openclaw/brave-api-key")
    BRIGHTDATA_API_KEY = _secret("BRIGHTDATA_API_KEY", "openclaw/brightdata-api-key")
    NIMBLEWAY_API_KEY = _secret("NIMBLEWAY_API_KEY", "openclaw/nimbleway-api-key")
    SCRAPINGBEE_API_KEY = _secret("SCRAPINGBEE_API_KEY", "openclaw/scrapingbee-api-key")
    _KEY_LOADED_AT = time.time()


def _running_on_ec2() -> bool:
    """Detect AWS EC2 via IMDS (supports both IMDSv1 and IMDSv2)."""
    try:
        import httpx as _httpx
        # IMDSv2: PUT to get a token — works even when IMDSv1 is disabled.
        r = _httpx.put(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            timeout=0.3,
        )
        if r.status_code == 200:
            return True
        # Fallback for IMDSv1-only configurations.
        r = _httpx.get("http://169.254.169.254/latest/meta-data/", timeout=0.3)
        return r.status_code == 200
    except Exception:
        return False

_DDG_LAST_CALL: float = 0.0
DDG_MIN_INTERVAL = 2.0

_BRAVE_QUOTA_EXHAUSTED: bool = False
_SERPER_QUOTA_EXHAUSTED: bool = False
_BRIGHTDATA_QUOTA_EXHAUSTED: bool = False
_NIMBLEWAY_QUOTA_EXHAUSTED: bool = False
_SCRAPINGBEE_QUOTA_EXHAUSTED: bool = False


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = ""
    published_date: str = ""
    _prefetched_text: Optional[str] = field(default=None)


# ──────────────────────────────────────────────
# Provider: SerpAPI (serpapi.com) news
# ──────────────────────────────────────────────

def _search_serpapi_news(
    query: str,
    limit: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[SearchResult]:
    if not SERPAPI_API_KEY:
        raise RuntimeError("SERPAPI_API_KEY not set")

    # SerpAPI news (tbm=nws) doesn't support site: operator — strip it.
    # Results are filtered by domain by the caller anyway.
    import re as _re
    clean_query = _re.sub(r"\bsite:\S+\s*", "", query).strip()

    params: dict = {
        "q": clean_query,
        "tbm": "nws",
        "num": min(limit, 100),
        "api_key": SERPAPI_API_KEY,
    }
    if date_from:
        params["tbs"] = f"cdr:1,cd_min:{date_from.month}/{date_from.day}/{date_from.year}"
        if date_to:
            params["tbs"] += f",cd_max:{date_to.month}/{date_to.day}/{date_to.year}"

    r = httpx.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=12,
    )
    r.raise_for_status()
    items = r.json().get("news_results", [])

    return [
        SearchResult(
            title=item.get("title", ""),
            url=item.get("link", ""),
            snippet=item.get("snippet", ""),
            source=item.get("source", _extract_domain(item.get("link", ""))),
            published_date=item.get("date", ""),
        )
        for item in items[:limit]
        if item.get("link")
    ]


# ──────────────────────────────────────────────
# Provider: Serper.dev /news
# ──────────────────────────────────────────────

def _search_serper_news(
    query: str,
    limit: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[SearchResult]:
    global _SERPER_QUOTA_EXHAUSTED
    if not SERPER_API_KEY:
        raise RuntimeError("SERPER_API_KEY not set")

    body: dict = {"q": query, "num": limit}
    if date_from and date_to:
        # Serper tbs date range: cdr:1,cd_min:M/D/YYYY,cd_max:M/D/YYYY
        def _fmt(dt: datetime) -> str:
            return f"{dt.month}/{dt.day}/{dt.year}"
        body["tbs"] = f"cdr:1,cd_min:{_fmt(date_from)},cd_max:{_fmt(date_to)}"

    r = httpx.post(
        "https://google.serper.dev/news",
        json=body,
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        timeout=10,
    )
    if r.status_code == 400 and "credits" in r.text.lower():
        _SERPER_QUOTA_EXHAUSTED = True
        raise RuntimeError("Serper quota exhausted (no credits)")
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
        "country": "us",
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
# Provider: BrightData SERP API
# ──────────────────────────────────────────────

def _search_brightdata(query: str, limit: int) -> List[SearchResult]:
    global _BRIGHTDATA_QUOTA_EXHAUSTED
    if not BRIGHTDATA_API_KEY:
        raise RuntimeError("BRIGHTDATA_API_KEY not set")

    search_url = "https://www.google.com/search?" + urlencode({"q": query, "gl": "us", "hl": "en"})
    r = httpx.post(
        "https://api.brightdata.com/request",
        json={"zone": "serp_api1", "url": search_url, "format": "raw"},
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {BRIGHTDATA_API_KEY}"},
        timeout=20,
    )
    if r.status_code in (401, 402):
        _BRIGHTDATA_QUOTA_EXHAUSTED = True
        raise RuntimeError(f"BrightData quota/auth error ({r.status_code})")
    r.raise_for_status()

    html = r.text
    result_pat = re.compile(r'href="(https://[^"#]+)"[^>]*>[^<]*<h3[^>]*class="LC20lb[^>]*>([^<]+)</h3>')
    snippet_pat = re.compile(r'class="VwiC3b[^"]*"[^>]*>(.*?)</div>')

    pairs = [(m.group(1), m.group(2)) for m in result_pat.finditer(html)]
    snippets = [re.sub(r'<[^>]+>', '', m.group(1)).strip() for m in snippet_pat.finditer(html)]

    return [
        SearchResult(
            title=title,
            url=url,
            snippet=snippets[i] if i < len(snippets) else "",
            source=_extract_domain(url),
        )
        for i, (url, title) in enumerate(pairs[:limit])
    ]


# ──────────────────────────────────────────────
# Provider: Nimbleway SERP API
# ──────────────────────────────────────────────

def _search_nimbleway(query: str, limit: int) -> List[SearchResult]:
    global _NIMBLEWAY_QUOTA_EXHAUSTED
    if not NIMBLEWAY_API_KEY:
        raise RuntimeError("NIMBLEWAY_API_KEY not set")

    r = httpx.post(
        "https://api.webit.live/api/v1/realtime/serp",
        json={"search_engine": "google_search", "country": "US", "query": query, "parse": True},
        headers={"Authorization": f"Bearer {NIMBLEWAY_API_KEY}", "Content-Type": "application/json"},
        timeout=20,
    )
    if r.status_code == 402:
        _NIMBLEWAY_QUOTA_EXHAUSTED = True
        raise RuntimeError("Nimbleway quota exhausted (402)")
    r.raise_for_status()

    data = r.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Nimbleway error: {data.get('status')}")

    items = data.get("parsing", {}).get("entities", {}).get("OrganicResult", [])
    return [
        SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("snippet", ""),
            source=item.get("cleaned_domain") or _extract_domain(item.get("url", "")),
        )
        for item in items[:limit]
        if item.get("url")
    ]


# ──────────────────────────────────────────────
# Provider: ScrapingBee Google Search
# ──────────────────────────────────────────────

def _search_scrapingbee(query: str, limit: int) -> List[SearchResult]:
    global _SCRAPINGBEE_QUOTA_EXHAUSTED
    if not SCRAPINGBEE_API_KEY:
        raise RuntimeError("SCRAPINGBEE_API_KEY not set")

    r = httpx.get(
        "https://app.scrapingbee.com/api/v1/store/google",
        params={"api_key": SCRAPINGBEE_API_KEY, "search": query, "nb_results": limit},
        timeout=20,
    )
    if r.status_code == 402:
        _SCRAPINGBEE_QUOTA_EXHAUSTED = True
        raise RuntimeError("ScrapingBee quota exhausted (402)")
    r.raise_for_status()

    data = r.json()
    items = (
        data.get("news_results")
        or data.get("top_stories")
        or data.get("organic_results")
        or []
    )
    return [
        SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("description", ""),
            source=item.get("domain") or _extract_domain(item.get("url", "")),
            published_date=item.get("date_utc") or item.get("date") or "",
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

    Tries providers in order, skipping any without a configured key or with
    an exhausted quota flag set for this process lifetime:
      SerpAPI → Serper.dev → Brave → BrightData → Nimbleway → ScrapingBee → DDG

    DDG is skipped on EC2 (AWS IPs are blocked by DDG/Yahoo).

    Args:
        query:     Search string. Include `site:domain.com` to restrict to a source.
        limit:     Max results to return.
        date_from: Optional start of date window.
        date_to:   Optional end of date window.

    Returns:
        List of SearchResult(title, url, snippet, source, published_date).
    """
    _refresh_keys_if_stale()
    _provider_local.name = "none"

    # 1. SerpAPI
    if SERPAPI_API_KEY:
        try:
            results = _search_serpapi_news(query, limit, date_from, date_to)
            if results:
                _provider_local.name = "serpapi"
                return results
            logger.warning("SerpAPI returned 0 results for: %s", query[:60])
        except Exception as e:
            logger.warning("SerpAPI failed: %s", e)

    # 2. Serper.dev news
    if SERPER_API_KEY and not _SERPER_QUOTA_EXHAUSTED:
        try:
            results = _search_serper_news(query, limit, date_from, date_to)
            if results:
                _provider_local.name = "serper"
                return results
            logger.warning("Serper returned 0 results for: %s", query[:60])
        except Exception as e:
            logger.warning("Serper failed: %s", e)

    # 3. Brave News
    if BRAVE_API_KEY and not _BRAVE_QUOTA_EXHAUSTED:
        try:
            results = _search_brave_news(query, limit, date_from, date_to)
            if results:
                _provider_local.name = "brave"
                return results
            logger.warning("Brave returned 0 results for: %s", query[:60])
        except Exception as e:
            logger.warning("Brave failed: %s", e)

    # 4. BrightData SERP API
    if BRIGHTDATA_API_KEY and not _BRIGHTDATA_QUOTA_EXHAUSTED:
        try:
            results = _search_brightdata(query, limit)
            if results:
                _provider_local.name = "brightdata"
                return results
            logger.warning("BrightData returned 0 results for: %s", query[:60])
        except Exception as e:
            logger.warning("BrightData failed: %s", e)

    # 5. Nimbleway SERP API
    if NIMBLEWAY_API_KEY and not _NIMBLEWAY_QUOTA_EXHAUSTED:
        try:
            results = _search_nimbleway(query, limit)
            if results:
                _provider_local.name = "nimbleway"
                return results
            logger.warning("Nimbleway returned 0 results for: %s", query[:60])
        except Exception as e:
            logger.warning("Nimbleway failed: %s", e)

    # 6. ScrapingBee Google Search
    if SCRAPINGBEE_API_KEY and not _SCRAPINGBEE_QUOTA_EXHAUSTED:
        try:
            results = _search_scrapingbee(query, limit)
            if results:
                _provider_local.name = "scrapingbee"
                return results
            logger.warning("ScrapingBee returned 0 results for: %s", query[:60])
        except Exception as e:
            logger.warning("ScrapingBee failed: %s", e)

    # 7. DuckDuckGo (free, no key) — skip on EC2: AWS IPs are blocked by DDG/Yahoo
    if not _running_on_ec2():
        try:
            results = _search_ddg_news(query, limit)
            if results:
                _provider_local.name = "ddg"
            return results
        except Exception as e:
            logger.warning("DDG failed: %s", e)
    else:
        logger.info("Skipping DDG (running on EC2)")

    logger.error("All search providers exhausted — no articles found for: %s", query[:60])
    return []


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    try:
        return re.sub(r"^www\.", "", __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url).netloc)
    except Exception:
        return ""
