"""
GDELT batch ingestor — fills data/raw_ingest/ for all events × sources.

Runs sequentially with 2s delay between API calls to stay within GDELT rate limits.
Retries on 429/5xx with exponential backoff.
Skips event×source pairs already in raw_ingest/.
After running, use: uv run python -m tm.orchestrator local_file

Usage:
    DATA_DIR=/path/to/data uv run python -m tm.gdelt_ingest
    DATA_DIR=/path/to/data uv run python -m tm.gdelt_ingest --events C05 C07 E07
    DATA_DIR=/path/to/data uv run python -m tm.gdelt_ingest --sources reuters toi
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

console = Console()

GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"

# Sources: (id, domain, language)
SOURCES = [
    ("reuters",      "reuters.com",           "en"),
    ("toi",          "timesofisrael.com",      "en"),
    ("haaretz",      "haaretz.com",            "en"),  # English edition
    ("jpost",        "jpost.com",              "en"),
    ("globes",       "en.globes.co.il",        "en"),  # English Globes
]

MVP_EVENTS = [
    "C05", "C06", "C07", "C08", "C09",
    "B04", "B08", "B09", "B10", "B11", "B13",
    "A04", "A12", "A13", "A14", "A15", "A19",
    "D02", "D03",
    "E07", "E08",
    "G02", "G05", "G06",
    "F05",
]


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


async def gdelt_search(
    domain: str,
    keywords: List[str],
    start_date: datetime,
    end_date: datetime,
    max_records: int = 10,
    retries: int = 4,
) -> List[Dict]:
    """
    Query GDELT Doc API. Returns list of {title, url, seendate}.
    Retries on 429/5xx with exponential backoff.
    """
    english_kws = [k.strip('"') for k in keywords if _is_ascii(k) and k.strip('"')]
    if not english_kws:
        return []

    # Build query: top keywords + domain
    kw_query = " OR ".join(f'"{kw}"' for kw in english_kws[:3])
    query = f"({kw_query}) domain:{domain}"

    start_str = start_date.strftime("%Y%m%d000000")
    end_str = (end_date - timedelta(days=1)).strftime("%Y%m%d235959")

    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "startdatetime": start_str,
        "enddatetime": end_str,
        "maxrecords": max_records,
        "sort": "DateDesc",
    }

    for attempt in range(retries):
        delay = 6.0 * (2 ** attempt)  # 6, 12, 24, 48 seconds
        if attempt > 0:
            console.print(f"    [dim]GDELT retry {attempt}/{retries-1} in {delay:.0f}s…[/dim]")
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(6.0)  # GDELT rate limit: 1 req / 5s (use 6s to be safe)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(GDELT_BASE, params=params)

            if r.status_code == 200:
                data = r.json()
                articles = []
                for art in data.get("articles", []):
                    pub = art.get("seendate", "")
                    try:
                        pub_str = datetime.strptime(pub[:8], "%Y%m%d").strftime("%Y-%m-%d")
                    except ValueError:
                        pub_str = start_date.strftime("%Y-%m-%d")
                    articles.append({
                        "title": art.get("title", ""),
                        "url": art.get("url", ""),
                        "date": pub_str,
                        "domain": art.get("domain", domain),
                    })
                return articles

            elif r.status_code in (429, 500, 502, 503):
                console.print(f"    [dim yellow]GDELT {r.status_code} — will retry[/dim yellow]")
                continue
            else:
                console.print(f"    [dim red]GDELT {r.status_code}[/dim red]")
                return []

        except Exception as e:
            console.print(f"    [dim red]GDELT error: {e}[/dim red]")
            if attempt == retries - 1:
                return []

    return []


async def fetch_full_text(url: str) -> str:
    """Scrape full article text, stripping navigation/scripts."""
    try:
        async with httpx.AsyncClient(
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TruthMachine/1.0)"},
            follow_redirects=True,
        ) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return ""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "figure"]):
            tag.extract()
        # Try to extract article body specifically
        for selector in ["article", "main", '[class*="article"]', '[class*="content"]']:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator=" ", strip=True)
                if len(text) > 300:
                    return text
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return ""


async def ingest_cell(
    event: dict,
    source_id: str,
    source_domain: str,
    raw_ingest_dir: Path,
    force: bool = False,
) -> int:
    """
    Fetch and save articles for one (event, source) pair.
    Returns number of articles saved.
    """
    cell_dir = raw_ingest_dir / source_id / event["id"]

    # Skip if already populated (unless --force)
    existing = list(cell_dir.glob("article_*.json")) if cell_dir.exists() else []
    if existing and not force:
        return len(existing)

    outcome_dt = datetime.strptime(event["outcome_date"], "%Y-%m-%d")
    window = int(event.get("predictive_window_days", 14))
    start_dt = outcome_dt - timedelta(days=window)

    results = await gdelt_search(
        domain=source_domain,
        keywords=event.get("duel_keywords") or event.get("search_keywords", []),
        start_date=start_dt,
        end_date=outcome_dt,
        max_records=5,
    )

    if not results:
        return 0

    cell_dir.mkdir(parents=True, exist_ok=True)
    saved = 0

    for i, art in enumerate(results[:5]):
        url = art.get("url", "")
        if not url:
            continue

        text = await fetch_full_text(url)
        if len(text) < 200:
            continue

        article = {
            "headline": art.get("title", ""),
            "text": text,
            "published_at": art.get("date", start_dt.strftime("%Y-%m-%d")),
            "author": "Unknown",
            "url": url,
        }

        out_path = cell_dir / f"article_{i+1:02d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(article, f, indent=2, ensure_ascii=False)
        saved += 1

    return saved


async def run_batch(
    data_dir: Path,
    event_ids: List[str],
    source_filter: Optional[List[str]],
    force: bool,
):
    events_dir = data_dir / "events"
    raw_ingest_dir = data_dir / "raw_ingest"

    # Load events
    events = {}
    for eid in event_ids:
        p = events_dir / f"{eid}.json"
        if p.exists():
            events[eid] = json.load(open(p))
        else:
            console.print(f"[yellow]Event {eid} not found, skipping[/yellow]")

    sources = [(sid, dom) for sid, dom, _ in SOURCES
               if source_filter is None or sid in source_filter]

    total = len(events) * len(sources)
    results: dict[str, dict] = {}  # eid → {sid: count}

    console.print(f"\n[bold]GDELT Batch Ingest[/bold]  {len(events)} events × {len(sources)} sources = {total} cells\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching…", total=total)

        for eid, event in events.items():
            results[eid] = {}
            for source_id, source_domain in sources:
                progress.update(task, description=f"[cyan]{eid}[/cyan] / [blue]{source_id}[/blue]")

                count = await ingest_cell(event, source_id, source_domain, raw_ingest_dir, force)
                results[eid][source_id] = count

                status = f"[green]{count} art[/green]" if count else "[dim]0[/dim]"
                console.print(f"  {eid}/{source_id}: {status}")
                progress.advance(task)

    # Summary table
    table = Table(title="Ingest Summary", show_header=True)
    table.add_column("Event", style="cyan")
    for sid, _ in sources:
        table.add_column(sid, justify="center")
    table.add_column("Total", justify="right", style="bold")

    grand_total = 0
    for eid in event_ids:
        if eid not in results:
            continue
        row = [eid]
        row_total = 0
        for sid, _ in sources:
            n = results[eid].get(sid, 0)
            row.append(str(n) if n else "·")
            row_total += n
        row.append(str(row_total))
        table.add_row(*row)
        grand_total += row_total

    console.print(table)
    console.print(f"\n[bold green]Total articles saved: {grand_total}[/bold green]")
    console.print(f"\nNext step: [bold]uv run python -m tm.orchestrator local_file[/bold]")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GDELT batch ingestor")
    parser.add_argument("--events", nargs="+", default=MVP_EVENTS, metavar="EID")
    parser.add_argument("--sources", nargs="+", default=None, metavar="SID")
    parser.add_argument("--force", action="store_true", help="Re-fetch already populated cells")
    args = parser.parse_args()

    data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
    asyncio.run(run_batch(data_dir, args.events, args.sources, args.force))


if __name__ == "__main__":
    main()
