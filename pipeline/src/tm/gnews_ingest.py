"""
Google News RSS + Wayback CDX batch ingestor.

Step 1a: Query Google News RSS with date operators to find article titles
         from the event's predictive window.
Step 1b: If GNews returns nothing → query Wayback CDX API to enumerate all
         archived article URLs from the domain in the date range (fallback).
Step 2:  Resolve each GNews title to a real URL via Brave Search API (primary)
         or DuckDuckGo (fallback).  CDX results already have URLs.
Step 3:  Scrape full article text via trafilatura (primary) with
         BeautifulSoup fallback.  CDX articles are fetched directly from
         Wayback to maximise historical coverage.

Sources: toi, jpost, haaretz, reuters, globes, ynet, israel_hayom,
         walla, n12, maariv, ch13, ch14, kan11  (Hebrew sources included)

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
import trafilatura
from bs4 import BeautifulSoup
from ddgs import DDGS
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

console = Console()

GNEWS_BASE = "https://news.google.com/rss/search"

# domain + GNews locale per source
# lang="en" → ASCII keyword, en-US GNews params
# lang="he" → first Hebrew keyword, iw-IL GNews params
SOURCES_CONFIG: Dict[str, Dict] = {
    # English sources
    "toi":          {"domain": "timesofisrael.com",  "lang": "en"},
    "jpost":        {"domain": "jpost.com",          "lang": "en"},
    "haaretz":      {"domain": "haaretz.com",        "lang": "en"},
    "reuters":      {"domain": "reuters.com",        "lang": "en"},
    "globes":       {"domain": "en.globes.co.il",    "lang": "en"},
    "ynet":         {"domain": "ynetnews.com",       "lang": "en"},
    "israel_hayom": {"domain": "israelhayom.com",    "lang": "en"},
    # Hebrew-native sources
    "walla":        {"domain": "news.walla.co.il",   "lang": "he"},
    "haaretz_he":   {"domain": "www.haaretz.co.il",  "lang": "he"},  # Hebrew edition — less paywalled than haaretz.com
    "n12":          {"domain": "www.mako.co.il",     "lang": "he"},
    "maariv":       {"domain": "www.maariv.co.il",   "lang": "he"},
    "ch13":         {"domain": "13tv.co.il",         "lang": "he"},
    "kan11":        {"domain": "www.kan.org.il",     "lang": "he"},
}

GNEWS_LOCALE = {
    "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "he": {"hl": "iw-IL", "gl": "IL", "ceid": "IL:iw"},
}

# Keep the old flat dict for backwards-compat callsites
SOURCES = {sid: cfg["domain"] for sid, cfg in SOURCES_CONFIG.items()}

MVP_EVENTS = [
    "C05", "C06", "C07", "C08", "C09",
    "B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09", "B10", "B11", "B12", "B13",
    "A04", "A12", "A13", "A14", "A15", "A19",
    "D02", "D03",
    "E07", "E08",
    "G02", "G05", "G06",
    "F04", "F05",
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

BRAVE_API_KEY: Optional[str] = os.environ.get("BRAVE_API_KEY")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


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
    lang: str = "en",
) -> List[Dict]:
    """
    Query Google News RSS for article titles in the date window.
    Returns list of {title, published_at}.
    lang="en" uses the first ASCII keyword + en-US locale.
    lang="he" uses the first non-ASCII (Hebrew) keyword + iw-IL locale.
    """
    if lang == "he":
        kws = [k.strip('"') for k in keywords if not _is_ascii(k) and k.strip('"')]
    else:
        kws = [k.strip('"') for k in keywords if _is_ascii(k) and k.strip('"')]

    if not kws:
        return []

    after = (start_date - timedelta(days=1)).strftime("%Y-%m-%d")
    before = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
    locale = GNEWS_LOCALE.get(lang, GNEWS_LOCALE["en"])

    # Try each keyword in order; stop at the first that returns results
    r = None
    for kw_part in kws:
        query = f"{kw_part} after:{after} before:{before} site:{domain}"
        params = {"q": query, **locale}
        try:
            r = httpx.get(GNEWS_BASE, params=params, headers=HEADERS, timeout=20, follow_redirects=True)
            if r.status_code != 200:
                continue
            # Peek at item count before full parse
            if "<item>" in r.text:
                break
        except Exception as e:
            console.print(f"    [dim red]GNews RSS error: {e}[/dim red]")
            r = None

    if r is None or r.status_code != 200:
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
    """Construct a probable article URL from title for domains with predictable slugs.
    Only TOI is reliable; all others fall through to DDG.
    """
    slug = _title_slug(title)
    if not slug:
        return None
    if domain == "timesofisrael.com":
        return f"https://www.timesofisrael.com/{slug}/"
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


def _filter_url(href: str, domain: str, expected_date: Optional[datetime]) -> bool:
    """Return True if the URL is a valid article candidate."""
    _BAD_PATHS = ("/authors/", "/author/", "/topics/", "/tag/", "/category/",
                  "/section/", "/search/", "/video/")
    if domain not in href:
        return False
    if any(p in href for p in _BAD_PATHS):
        return False
    if expected_date:
        url_dt = _url_date(href)
        if url_dt and abs((url_dt - expected_date).days) > 30:
            return False
    return True


def resolve_url_via_brave(
    title: str, domain: str, expected_date: Optional[datetime] = None
) -> Optional[str]:
    """Resolve article URL using Brave Search API (no rate limiting, higher quality)."""
    if not BRAVE_API_KEY:
        return None
    query = f'site:{domain} {title[:80]}'
    try:
        r = httpx.get(
            BRAVE_SEARCH_URL,
            params={"q": query, "count": 5, "search_lang": "en"},
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        results = r.json().get("web", {}).get("results", [])
        for res in results:
            href = res.get("url", "")
            if _filter_url(href, domain, expected_date):
                return href
    except Exception as e:
        console.print(f"    [dim red]Brave error: {e}[/dim red]")
    return None


def resolve_url_via_ddg(
    title: str, domain: str, expected_date: Optional[datetime] = None
) -> Optional[str]:
    """Fallback: resolve article URL via DuckDuckGo (rate-limited, free)."""
    global _DDG_LAST_CALL
    elapsed = time.time() - _DDG_LAST_CALL
    if elapsed < DDG_MIN_INTERVAL:
        time.sleep(DDG_MIN_INTERVAL - elapsed)
    query = f'site:{domain} "{title[:60]}"'
    try:
        with DDGS() as d:
            results = list(d.text(query, max_results=5))
        _DDG_LAST_CALL = time.time()
        for r in results:
            href = r.get("href", "")
            if _filter_url(href, domain, expected_date):
                return href
    except Exception as e:
        console.print(f"    [dim red]DDG error: {e}[/dim red]")
        _DDG_LAST_CALL = time.time()
    return None


def resolve_url(
    title: str, domain: str, expected_date: Optional[datetime] = None
) -> Optional[str]:
    """
    Find the real article URL. Tries in order:
      1. Construct URL directly from title slug (instant, works for TOI)
      2. Brave Search API (fast, reliable, no rate limits)
      3. DuckDuckGo (free fallback, rate-limited)
    """
    direct = _construct_url(title, domain)
    if direct:
        try:
            r = httpx.get(direct, headers=HEADERS, timeout=10, follow_redirects=True)
            if r.status_code == 200 and len(r.text) > 500:
                return str(r.url)
        except Exception:
            pass

    url = resolve_url_via_brave(title, domain, expected_date)
    if url:
        return url

    return resolve_url_via_ddg(title, domain, expected_date)


PAYWALL_THRESHOLD = 500  # chars — below this, try Wayback Machine


async def _scrape_html(html: str) -> str:
    """Extract article body: trafilatura primary, BeautifulSoup fallback."""
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
        favor_precision=False,
    )
    if text and len(text) > 300:
        return text
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "figure"]):
        tag.extract()
    for sel in ["article", "main", ".article-body", ".article-content", ".post-content",
                '[class*="article"]', '[class*="story"]']:
        el = soup.select_one(sel)
        if el:
            t = el.get_text(separator=" ", strip=True)
            if len(t) > 300:
                return t
    return soup.get_text(separator=" ", strip=True)


async def _fetch_wayback(url: str, client: httpx.AsyncClient) -> str:
    """Try Wayback Machine for a cached copy of a paywalled/blocked URL."""
    try:
        wb_url = f"https://web.archive.org/web/{url}"
        r = await client.get(wb_url, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            return ""
        return await _scrape_html(r.text)
    except Exception as e:
        console.print(f"    [dim]Wayback failed: {e}[/dim]")
        return ""


CDX_API = "http://web.archive.org/cdx/search/cdx"
CDX_FETCH_LIMIT = 15   # max candidates to actually fetch per cell
CDX_SCAN_LIMIT  = 150  # max CDX rows to download before filtering


async def search_wayback_cdx(
    domain: str,
    start_date: datetime,
    end_date: datetime,
    keywords: List[str],
    max_results: int = 5,
) -> List[Dict]:
    """
    Enumerate archived article URLs for *domain* in [start_date, end_date]
    via the Wayback CDX API, then fetch up to *max_results* articles from
    Wayback.  Used as a fallback when Google News RSS returns nothing.

    Returns list of {url, published_at, headline, text}.
    """
    # Strip www. — matchType=domain covers all subdomains
    cdx_domain = re.sub(r"^www\.", "", domain)
    params = [
        ("url",       cdx_domain),
        ("matchType", "domain"),
        ("output",    "json"),
        ("from",      start_date.strftime("%Y%m%d")),
        ("to",        end_date.strftime("%Y%m%d")),
        ("limit",     str(CDX_SCAN_LIMIT)),
        ("filter",    "mimetype:text/html"),
        ("filter",    "statuscode:200"),
        ("fl",        "original,timestamp"),
        ("collapse",  "urlkey"),
    ]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(CDX_API, params=params)
        if r.status_code != 200:
            return []
        rows = r.json()
    except Exception as e:
        console.print(f"    [dim red]CDX error: {e}[/dim red]")
        return []

    if len(rows) < 2:   # first row is header ["original","timestamp"]
        return []

    # ── Filter to article-like URLs ──────────────────────────────────────────
    candidates: List[tuple] = []
    for original, timestamp in rows[1:]:
        if not _filter_url(original, domain, None):
            continue
        try:
            pub_dt = datetime.strptime(timestamp[:8], "%Y%m%d")
        except ValueError:
            continue
        if not (start_date <= pub_dt <= end_date):
            continue
        candidates.append((original, timestamp, pub_dt))

    if not candidates:
        return []

    # ── Score by keyword presence in URL path ────────────────────────────────
    ascii_kws = [k.lower() for k in keywords if _is_ascii(k)]
    if ascii_kws:
        def _score(url: str) -> int:
            u = url.lower()
            return sum(1 for kw in ascii_kws if kw.replace(" ", "-") in u or kw.replace(" ", "") in u)
        candidates.sort(key=lambda x: -_score(x[0]))

    fetch_pool = candidates[:CDX_FETCH_LIMIT]
    console.print(f"    [dim]CDX: {len(candidates)} candidates → fetching {len(fetch_pool)}[/dim]")

    # ── Fetch from Wayback ───────────────────────────────────────────────────
    results: List[Dict] = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for original, timestamp, pub_dt in fetch_pool:
            if len(results) >= max_results:
                break
            wb_url = f"https://web.archive.org/web/{timestamp}/{original}"
            try:
                r = await client.get(wb_url)
                if r.status_code != 200:
                    continue
                html = r.text

                # Extract headline via trafilatura metadata
                meta = trafilatura.extract_metadata(html)
                headline = (meta.title or "") if meta else ""

                text = await _scrape_html(html)
                if len(text) < 300:
                    continue

                results.append({
                    "url":          original,
                    "published_at": pub_dt.strftime("%Y-%m-%d"),
                    "headline":     headline,
                    "text":         text,
                })
                await asyncio.sleep(0.5)
            except Exception as e:
                console.print(f"    [dim]CDX fetch failed: {e}[/dim]")
                continue

    return results


async def fetch_article_text(url: str) -> str:
    """
    Scrape full article text from URL.
    1. trafilatura (primary) + BeautifulSoup fallback
    2. If result < PAYWALL_THRESHOLD chars → try Wayback Machine cached copy
    """
    try:
        async with httpx.AsyncClient(
            headers=HEADERS, timeout=25, follow_redirects=True
        ) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return ""
            text = await _scrape_html(r.text)

            if len(text) < PAYWALL_THRESHOLD:
                console.print(f"    [dim]Short article ({len(text)} chars), trying Wayback...[/dim]")
                wb_text = await _fetch_wayback(url, client)
                if len(wb_text) > len(text):
                    console.print(f"    [dim green]Wayback: {len(wb_text)} chars[/dim green]")
                    return wb_text

            return text
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

    cfg = SOURCES_CONFIG.get(source_id)
    if not cfg:
        return 0
    domain = cfg["domain"]
    lang = cfg.get("lang", "en")

    outcome_dt = datetime.strptime(event["outcome_date"], "%Y-%m-%d")
    window = int(event.get("predictive_window_days", 14))
    start_dt = outcome_dt - timedelta(days=window)

    keywords = event.get("search_keywords", [])

    candidates = search_gnews_rss(
        domain=domain,
        keywords=keywords,
        start_date=start_dt,
        end_date=outcome_dt,
        lang=lang,
    )

    cell_dir.mkdir(parents=True, exist_ok=True)
    saved = 0

    if candidates:
        # ── GNews path: resolve URL then scrape ──────────────────────────────
        for art in candidates[:5]:
            expected_dt = datetime.strptime(art["published_at"], "%Y-%m-%d")
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(
                None, resolve_url, art["title"], domain, expected_dt
            )
            if not url:
                console.print(f"    [dim]No URL for '{art['title'][:50]}'[/dim]")
                continue

            await asyncio.sleep(1.0)
            text = await fetch_article_text(url)
            if len(text) < 250:
                continue

            article = {
                "headline": art["title"],
                "text":     text,
                "published_at": art["published_at"],
                "author":   "Unknown",
                "url":      url,
            }
            out = cell_dir / f"article_{saved+1:02d}.json"
            out.write_text(json.dumps(article, indent=2, ensure_ascii=False))
            saved += 1
    else:
        # ── CDX fallback: enumerate Wayback archives ─────────────────────────
        console.print(f"    [dim]GNews empty → CDX fallback for {source_id}/{event['id']}[/dim]")
        cdx_arts = await search_wayback_cdx(domain, start_dt, outcome_dt, keywords)
        for art in cdx_arts:
            article = {
                "headline": art["headline"],
                "text":     art["text"],
                "published_at": art["published_at"],
                "author":   "Unknown",
                "url":      art["url"],
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

    sources = [s for s in SOURCES_CONFIG if source_filter is None or s in source_filter]
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
