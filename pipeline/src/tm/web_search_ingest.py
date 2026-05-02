"""
Web Search batch ingestor — uses the same search stack as daatan.

Provider chain: DataForSEO → SerpAPI → Serper → Brave (first available).
All providers support date-filtered historical queries via Google's CDR parameter,
giving much better pre-event article coverage than GDELT's domain filter.

Results land in data/raw_ingest/web_search/{event_id}/, same schema as
gdelt_ingest.py and site_search.py, so the orchestrator picks them up unchanged.

Usage:
    DATA_DIR=/path/to/data uv run python -m tm.web_search_ingest
    DATA_DIR=/path/to/data uv run python -m tm.web_search_ingest --events C07 B10 A19
    DATA_DIR=/path/to/data uv run python -m tm.web_search_ingest --events C07 --limit 15 --force
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

from tm import web_search as _ws

console = Console()

DUEL_EVENTS = [
    "A19", "B04", "B05", "B08", "B09", "B10",
    "C07", "C08", "C09", "E07", "E08",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}


from .utils import _is_ascii



async def _fetch_text(url: str) -> str:
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=25, follow_redirects=True) as c:
            r = await c.get(url)
            if r.status_code != 200:
                return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "figure"]):
            tag.extract()
        for sel in ["article", "main", ".article-body", ".article-content",
                    '[class*="article"]', '[class*="story"]']:
            el = soup.select_one(sel)
            if el:
                t = el.get_text(separator=" ", strip=True)
                if len(t) > 300:
                    return t
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return ""


async def ingest_event(
    event: dict,
    raw_ingest_dir: Path,
    limit: int,
    force: bool,
) -> int:
    eid = event["id"]
    cell_dir = raw_ingest_dir / "web_search" / eid
    existing = list(cell_dir.glob("article_*.json")) if cell_dir.exists() else []
    if existing and not force:
        return len(existing)

    outcome_dt = datetime.strptime(event["outcome_date"], "%Y-%m-%d")
    window = int(event.get("predictive_window_days", 30))
    start_dt = outcome_dt - timedelta(days=window)

    keywords = event.get("duel_keywords") or event.get("search_keywords", [])
    ascii_kws = [k for k in keywords if _is_ascii(k)]
    if not ascii_kws:
        console.print(f"  [dim yellow]{eid}: no ASCII keywords, skipping[/dim yellow]")
        return 0

    # Collect unique URLs across up to 3 keyword queries
    seen_urls: set[str] = set()
    candidates: list[_ws.SearchResult] = []

    for kw in ascii_kws[:3]:
        try:
            results = await asyncio.to_thread(
                _ws.search_articles, kw, limit, start_dt, outcome_dt
            )
            for r in results:
                if r.url and r.url not in seen_urls:
                    seen_urls.add(r.url)
                    candidates.append(r)
            provider = getattr(_ws._provider_local, "name", "?")
            console.print(
                f"  [dim]{eid} «{kw[:40]}»: {len(results)} hits via {provider}[/dim]"
            )
        except Exception as e:
            console.print(f"  [dim red]{eid} search error: {e}[/dim red]")
        await asyncio.sleep(1.0)

    if not candidates:
        return 0

    cell_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    article_idx = len(existing)  # continue numbering if partially populated

    for result in candidates[:limit]:
        await asyncio.sleep(1.0)
        text = await _fetch_text(result.url)
        if len(text) < 250:
            continue

        pub_date = (result.published_date or "")[:10] or start_dt.strftime("%Y-%m-%d")
        article = {
            "headline": result.title,
            "text": text,
            "published_at": pub_date,
            "estimated_date": not bool((result.published_date or "")[:10]),
            "author": "Unknown",
            "url": result.url,
            "snippet": result.snippet,
        }
        article_idx += 1
        out = cell_dir / f"article_{article_idx:02d}.json"
        out.write_text(json.dumps(article, indent=2, ensure_ascii=False))
        saved += 1

    return saved


async def run_batch(
    data_dir: Path,
    event_ids: List[str],
    limit: int,
    force: bool,
):
    events_dir = data_dir / "events"
    raw_ingest_dir = data_dir / "raw_ingest"

    events: dict[str, dict] = {}
    for eid in event_ids:
        p = events_dir / f"{eid}.json"
        if p.exists():
            events[eid] = json.loads(p.read_text())
        else:
            console.print(f"[yellow]Event {eid} not found, skipping[/yellow]")

    console.print(
        f"\n[bold]Web Search Ingest[/bold]  "
        f"{len(events)} events · up to {limit} articles each\n"
    )

    # Show which provider is active
    _ws._refresh_keys_if_stale()
    configured = [
        name for name, key in [
            ("dataforseo", _ws.DATAFORSEO_API_KEY),
            ("serpapi",    _ws.SERPAPI_API_KEY),
            ("serper",     _ws.SERPER_API_KEY),
            ("brave",      _ws.BRAVE_API_KEY),
        ] if key
    ]
    console.print(f"Configured providers: [cyan]{', '.join(configured) or 'none'}[/cyan]\n")

    results: dict[str, int] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(), MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching…", total=len(events))

        for eid, event in events.items():
            progress.update(task, description=f"[cyan]{eid}[/cyan] — {event['name'][:40]}")
            count = await ingest_event(event, raw_ingest_dir, limit, force)
            results[eid] = count
            label = f"[green]{count} saved[/green]" if count else "[dim]0[/dim]"
            console.print(f"  {eid}: {label}")
            progress.advance(task)

    table = Table(title="Web Search Ingest Summary")
    table.add_column("Event", style="cyan")
    table.add_column("Articles saved", justify="right")

    grand = 0
    for eid in event_ids:
        if eid not in results:
            continue
        n = results[eid]
        table.add_row(eid, str(n) if n else "·")
        grand += n

    console.print(table)
    console.print(f"\n[bold green]Total articles saved: {grand}[/bold green]")
    console.print(
        f"Next: [bold]DATA_DIR={data_dir} uv run python -m tm.orchestrator local_file[/bold]"
    )


def main():
    import argparse
    p = argparse.ArgumentParser(description="Web Search batch ingestor for duel events")
    p.add_argument("--events", nargs="+", default=DUEL_EVENTS, metavar="EID")
    p.add_argument("--limit", type=int, default=10, help="Max articles per event (default 10)")
    p.add_argument("--force", action="store_true", help="Re-fetch already populated cells")
    args = p.parse_args()

    data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
    asyncio.run(run_batch(data_dir, args.events, args.limit, args.force))


if __name__ == "__main__":
    main()
