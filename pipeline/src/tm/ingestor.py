"""
Article ingestors.

DDGIngestor    — DuckDuckGo search (free, no key, good historical coverage) [default]
GDELTIngestor  — GDELT Doc 2.0 API (free, no key, rate-limited to ~1 req/s)
BraveIngestor  — Brave Search API (paid, fastest when quota available)
"""

import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Dict
from rich.console import Console

console = Console()


class DDGIngestor:
    """
    Uses the duckduckgo_search package (no API key, no quota).
    Filters results to the given date window by checking snippet date hints.
    """

    async def search(
        self,
        source_domain: str,
        keywords: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict]:
        from ddgs import DDGS

        english_kws = [k.strip('"') for k in keywords if _is_ascii(k)]
        if not english_kws:
            console.print(f"    [dim]DDG: no ASCII keywords for {source_domain}[/dim]")
            return []

        year = start_date.year
        after = (start_date - timedelta(days=1)).strftime("%Y-%m-%d")
        before = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
        query = (
            " ".join(english_kws[:2])
            + f" site:{source_domain}"
            + f" after:{after} before:{before}"
        )
        console.print(f"    [dim]DDG: {query[:90]}[/dim]")

        try:
            # Run blocking DDG call in a thread so we don't block the event loop
            results = await asyncio.to_thread(_ddg_search, query, max_results=10)
        except Exception as e:
            console.print(f"    [dim red]DDG error: {e}[/dim red]")
            return []

        cutoff_before = end_date - timedelta(days=1)
        articles = []
        for r in results:
            articles.append({
                "headline": r.get("title", ""),
                "text": r.get("body", r.get("snippet", "")),
                "published_at": _parse_ddg_date(r, start_date),
                "author": "Unknown",
                "url": r.get("href") or r.get("url", ""),
            })

        console.print(f"    [dim]DDG: {len(articles)} results for {source_domain}[/dim]")
        return articles


def _ddg_search(query: str, max_results: int = 10) -> List[Dict]:
    from ddgs import DDGS
    with DDGS() as ddgs:
        # Try news search first (richer date metadata), fall back to text
        try:
            results = list(ddgs.news(query, max_results=max_results))
            if results:
                return results
        except Exception:
            pass
        return list(ddgs.text(query, max_results=max_results))


def _parse_ddg_date(result: dict, fallback: datetime) -> str:
    """Try to extract a date from DDG result metadata."""
    for field in ("date", "published", "pubdate", "pub_date"):
        val = result.get(field)
        if val:
            try:
                # DDG news: "2024-04-13T14:22:00+00:00" or "2024-04-13"
                return datetime.fromisoformat(str(val)[:10]).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return fallback.strftime("%Y-%m-%d")


class GDELTIngestor:
    """
    GDELT DOC 2.0 — free, no key, rate-limit ~1 req/sec.
    """

    BASE = "https://api.gdeltproject.org/api/v2/doc/doc"

    async def search(
        self,
        source_domain: str,
        keywords: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict]:
        english_kws = [k.strip('"') for k in keywords if _is_ascii(k)]
        if not english_kws:
            return []

        query = " OR ".join(f'"{kw}"' for kw in english_kws[:3])
        query += f" domain:{source_domain}"
        start_str = start_date.strftime("%Y%m%d000000")
        end_str = (end_date - timedelta(days=1)).strftime("%Y%m%d235959")

        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "startdatetime": start_str,
            "enddatetime": end_str,
            "maxrecords": 10,
            "sort": "DateDesc",
        }

        await asyncio.sleep(1.2)  # stay under 1 req/s rate limit
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(self.BASE, params=params)
                if r.status_code != 200:
                    return []
                data = r.json()
        except Exception as e:
            console.print(f"    [dim red]GDELT: {e}[/dim red]")
            return []

        articles = []
        for art in data.get("articles", []):
            pub = art.get("seendate", "")
            try:
                pub_str = datetime.strptime(pub[:8], "%Y%m%d").strftime("%Y-%m-%d")
            except ValueError:
                pub_str = start_date.strftime("%Y-%m-%d")
            articles.append({
                "headline": art.get("title", ""),
                "text": art.get("title", ""),
                "published_at": pub_str,
                "author": art.get("author", "Unknown"),
                "url": art.get("url", ""),
            })
        return articles


class BraveIngestor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.search.brave.com/res/v1/web/search"

    async def search(
        self,
        source_domain: str,
        keywords: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict]:
        cutoff = end_date - timedelta(days=1)
        query = (
            f"{' '.join(keywords)} site:{source_domain} "
            f"after:{start_date.strftime('%Y-%m-%d')} before:{cutoff.strftime('%Y-%m-%d')}"
        )
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        async with httpx.AsyncClient() as client:
            r = await client.get(self.base_url, headers=headers, params={"q": query, "count": 10})
            if r.status_code != 200:
                console.print(f"    [dim red]Brave {r.status_code}[/dim red]")
                return []
            return [
                {
                    "headline": res.get("title"),
                    "text": res.get("description", ""),
                    "published_at": res.get("page_age", end_date.strftime("%Y-%m-%d")),
                    "author": "Unknown",
                    "url": res.get("url"),
                }
                for res in r.json().get("web", {}).get("results", [])
            ]


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False
