"""
Google News RSS + DDG batch ingestor — no API keys, no rate limits.

Step 1: Query Google News RSS with date operators to find article titles
        from the event's predictive window.
Step 2: Resolve each title to a real URL via DuckDuckGo site-search.
Step 3: Scrape full article text and save to data/raw_ingest/.

Sources: toi, jpost, haaretz, reuters, globes

Usage:
    DATA_DIR=/path/to/data uv run python -m tm.gnews_ingest
    DATA_DIR=/path/to/data uv run python -m tm.gnews_ingest --events C05 E07 --sources toi jpost
"""

import asyncio
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Dict, Optional

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

console = Console()

GNEWS_BASE = "https://news.google.com/rss/search"

SOURCES = {
    "toi":     "timesofisrael.com",
    "jpost":   "jpost.com",
    "haaretz": "haaretz.com",
    "reuters": "reuters.com",
    "globes":  "en.globes.co.il",
}

MVP_EVENTS = [
    "C05", "C06", "C07", "C08", "C09",
    "B04", "B08", "B09", "B10", "B11", "B13",
    "A04", "A12", "A13", "A14", "A15", "A19",
    "D02", "D03",
    "E07", "E08",
    "G02", "G05", "G06",
    "F05",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

_DDG_LAST_CALL: float = 0.0
DDG_MIN_INTERVAL = 2.0  # seconds between DDG calls


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _clean_title(title: str) -> str:
    """Strip publisher suffix like ' - The Times of Israel'."""
    for sep in [" - ", " | ", " — "]:
        if sep in title:
            title = title.rsplit(sep, 1)[0]
    return title.strip()


def search_gnews_rss(
    domain: str,
    keywords: List[str],
    start_date: datetime,
    end_date: datetime,
    max_results: int = 10,
) -> List[Dict]:
    """
    Query Google News RSS for article titles in the date window.
    Returns list of {title, published_at}.
    """
    ascii_kws = [k.strip('"') for k in keywords if _is_ascii(k) and k.strip('"')]
    if not ascii_kws:
        return []

    # Use only the most specific single keyword phrase for GNews (more gives 0 results)
    kw_part = ascii_kws[0] if ascii_kws else ""
    after = (start_date - timedelta(days=1)).strftime("%Y-%m-%d")
    before = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
    query = f"{kw_part} after:{after} before:{before} site:{domain}"

    params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}

    try:
        r = httpx.get(GNEWS_BASE, params=params, headers=HEADERS, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            console.print(f"    [dim red]GNews RSS {r.status_code}[/dim red]")
            return []
    except Exception as e:
        console.print(f"    [dim red]GNews RSS error: {e}[/dim red]")
        return []

    articles = []
    try:
        root = ET.fromstring(r.text)
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item"):
            title_raw = item.findtext("title", "")
            pubdate_str = item.findtext("pubDate", "")

            title = _clean_title(title_raw)
            if not title:
                continue

            try:
                pub_dt = parsedate_to_datetime(pubdate_str).replace(tzinfo=None)
            except Exception:
                pub_dt = None

            # Strict date filter
            if pub_dt and not (start_date <= pub_dt <= end_date):
                continue

            pub_str = pub_dt.strftime("%Y-%m-%d") if pub_dt else start_date.strftime("%Y-%m-%d")
            articles.append({"title": title, "published_at": pub_str})

            if len(articles) >= max_results:
                break
    except ET.ParseError as e:
        console.print(f"    [dim red]RSS parse error: {e}[/dim red]")
        return []

    return articles


def _title_slug(title: str) -> str:
    """Convert title to URL slug (lowercase, ASCII, hyphen-separated)."""
    t = title.lower()
    t = re.sub(r"['\",.:;!?()\[\]{}&|+=%#@$\\\\/]", "", t)
    t = re.sub(r"[^a-z0-9\s-]", "", t)
    t = re.sub(r"\s+", "-", t.strip())
    return re.sub(r"-+", "-", t)


def _construct_url(title: str, domain: str) -> Optional[str]:
    """Construct a probable article URL from title for known domains."""
    slug = _title_slug(title)
    if not slug:
        return None
    if domain == "timesofisrael.com":
        return f"https://www.timesofisrael.com/{slug}/"
    # JPost URLs: /article/{slug} or /israel-news/{slug} — try /article/ first
    if domain == "jpost.com":
        return f"https://www.jpost.com/article/{slug}"
    # Reuters: /world/middle-east/{slug}-{date} — harder to construct, skip
    return None


def _url_date(url: str) -> Optional[datetime]:
    """Extract date from URL pattern like /2024/04/12/ or -2024-04-12."""
    m = re.search(r"[/\-](20\d\d)[/\-](\d\d)[/\-](\d\d)", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def resolve_url(
    title: str, domain: str, expected_date: Optional[datetime] = None
) -> Optional[str]:
    """
    Find the real article URL. Tries:
      1. Construct URL directly from title slug (fast, works for TOI/JPost)
      2. DDG site search as fallback
    """
    # Try direct URL construction first (no network for TOI/JPost)
    direct = _construct_url(title, domain)
    if direct:
        try:
            r = httpx.get(direct, headers=HEADERS, timeout=10, follow_redirects=True)
            if r.status_code == 200 and len(r.text) > 500:
                return str(r.url)
        except Exception:
            pass

    # Fall back to DDG
    return resolve_url_via_ddg(title, domain, expected_date)


def resolve_url_via_ddg(
    title: str, domain: str, expected_date: Optional[datetime] = None
) -> Optional[str]:
    """Find the real article URL using DDG title search.
    Optionally verify that the URL's date is within ±30 days of expected_date."""
    global _DDG_LAST_CALL
    elapsed = time.time() - _DDG_LAST_CALL
    if elapsed < DDG_MIN_INTERVAL:
        time.sleep(DDG_MIN_INTERVAL - elapsed)

    query = f'site:{domain} "{title[:60]}"'
    try:
        with DDGS() as d:
            results = list(d.text(query, max_results=5))
        _DDG_LAST_CALL = time.time()
        _BAD_PATHS = ("/authors/", "/author/", "/topics/", "/tag/", "/category/",
                      "/section/", "/search/", "/video/")
        for r in results:
            href = r.get("href", "")
            if domain not in href:
                continue
            if any(p in href for p in _BAD_PATHS):
                continue
            if expected_date:
                url_dt = _url_date(href)
                if url_dt and abs((url_dt - expected_date).days) > 30:
                    continue  # date mismatch — skip
            return href
    except Exception as e:
        console.print(f"    [dim red]DDG error: {e}[/dim red]")
        _DDG_LAST_CALL = time.time()
    return None


async def fetch_article_text(url: str) -> str:
    """Scrape full article text from URL."""
    try:
        async with httpx.AsyncClient(
            headers=HEADERS, timeout=25, follow_redirects=True
        ) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "figure"]):
            tag.extract()
        for sel in ["article", "main", ".article-body", ".article-content", ".post-content",
                    '[class*="article"]', '[class*="story"]', '[class*="content"]']:
            el = soup.select_one(sel)
            if el:
                t = el.get_text(separator=" ", strip=True)
                if len(t) > 300:
                    return t
        return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        console.print(f"    [dim red]scrape error: {e}[/dim red]")
        return ""


async def ingest_cell(
    event: dict,
    source_id: str,
    raw_ingest_dir: Path,
    force: bool = False,
) -> int:
    """
    Fetch and save articles for one (event, source) cell.
    Returns number of articles saved.
    """
    cell_dir = raw_ingest_dir / source_id / event["id"]
    existing = list(cell_dir.glob("article_*.json")) if cell_dir.exists() else []
    if existing and not force:
        return len(existing)

    domain = SOURCES.get(source_id)
    if not domain:
        return 0

    outcome_dt = datetime.strptime(event["outcome_date"], "%Y-%m-%d")
    window = int(event.get("predictive_window_days", 14))
    start_dt = outcome_dt - timedelta(days=window)

    candidates = search_gnews_rss(
        domain=domain,
        keywords=event.get("search_keywords", []),
        start_date=start_dt,
        end_date=outcome_dt,
    )

    if not candidates:
        return 0

    cell_dir.mkdir(parents=True, exist_ok=True)
    saved = 0

    for i, art in enumerate(candidates[:5]):
        # Resolve real URL (try direct construction first, then DDG)
        expected_dt = datetime.strptime(art["published_at"], "%Y-%m-%d")
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None, resolve_url, art["title"], domain, expected_dt
        )
        if not url:
            console.print(f"    [dim]DDG: no URL for '{art['title'][:50]}'[/dim]")
            continue

        await asyncio.sleep(1.0)

        text = await fetch_article_text(url)
        if len(text) < 250:
            continue

        article = {
            "headline": art["title"],
            "text": text,
            "published_at": art["published_at"],
            "author": "Unknown",
            "url": url,
        }
        out = cell_dir / f"article_{saved+1:02d}.json"
        out.write_text(json.dumps(article, indent=2, ensure_ascii=False))
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

    events = {}
    for eid in event_ids:
        p = events_dir / f"{eid}.json"
        if p.exists():
            events[eid] = json.load(open(p))
        else:
            console.print(f"[yellow]Event {eid} not found, skipping[/yellow]")

    sources = [s for s in SOURCES if source_filter is None or s in source_filter]
    total = len(events) * len(sources)

    console.print(
        f"\n[bold]Google News + DDG Batch Ingest[/bold]  "
        f"{len(events)} events × {len(sources)} sources = {total} cells\n"
    )

    results: dict[str, dict] = {}

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
            for sid in sources:
                progress.update(task, description=f"[cyan]{eid}[/cyan]/[blue]{sid}[/blue]")
                count = await ingest_cell(event, sid, raw_ingest_dir, force)
                results[eid][sid] = count
                label = f"[green]{count} art[/green]" if count else "[dim]0[/dim]"
                console.print(f"  {eid}/{sid}: {label}")
                progress.advance(task)
                await asyncio.sleep(1.0)

    # Summary table
    table = Table(title="Ingest Summary")
    table.add_column("Event", style="cyan")
    for sid in sources:
        table.add_column(sid, justify="center")
    table.add_column("Total", justify="right", style="bold")

    grand = 0
    for eid in event_ids:
        if eid not in results:
            continue
        row = [eid]
        t = 0
        for sid in sources:
            n = results[eid].get(sid, 0)
            row.append(str(n) if n else "·")
            t += n
        row.append(str(t))
        table.add_row(*row)
        grand += t

    console.print(table)
    console.print(f"\n[bold green]Total articles saved: {grand}[/bold green]")
    console.print(
        f"Next: [bold]DATA_DIR={data_dir} uv run python -m tm.orchestrator local_file[/bold]"
    )


def main():
    import argparse
    p = argparse.ArgumentParser(description="Google News RSS + DDG batch ingestor")
    p.add_argument("--events", nargs="+", default=MVP_EVENTS)
    p.add_argument("--sources", nargs="+", default=None)
    p.add_argument("--force", action="store_true", help="Re-fetch already populated cells")
    args = p.parse_args()

    data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
    asyncio.run(run_batch(data_dir, args.events, args.sources, args.force))


if __name__ == "__main__":
    main()
