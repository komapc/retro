"""
Polymarket Harvest — bulk download of resolved political/geopolitical markets.

Fetches all resolved binary markets from the Gamma API (2023-01-01 to today),
filters to political/geopolitical categories, validates outcome clarity, and
writes data/poc/pm_harvest/events.jsonl for poc_event_gen.py to consume.

Usage:
    python -m tm.polymarket_harvest
    python -m tm.polymarket_harvest --data-dir /path/to/data/poc --start 2024-01-01

Output:
    data/poc/pm_harvest/events.jsonl   — one JSON object per line
    data/poc/pm_harvest/raw_page_N.json — cached raw API pages (resumable)
"""

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

logger = logging.getLogger(__name__)
console = Console()

GAMMA_BASE = "https://gamma-api.polymarket.com"
PAGE_SIZE = 100
REQUEST_DELAY = 0.5  # seconds between pages (be polite)

# Polymarket category values to include (exact match, case-insensitive)
# NOTE: only old (<2022) markets have categories populated; newer ones are empty.
POLITICAL_CATEGORIES = {
    "global politics",
    "us-current-affairs",
    "politics",
    "elections",
    "geopolitics",
    "world",
}

# Keyword fragments — question must contain at least one (case-insensitive)
POLITICAL_KEYWORDS = [
    # Electoral
    "election", "elect", "vote", "ballot", "candidate", "primary", "runoff",
    "inaugur", "senate", "congress", "parliament", "referendum", "poll ",
    # Leadership
    "president", "prime minister", "chancellor", "premier", "minister",
    "trump", "biden", "harris", "zelensky", "putin", "macron", "scholz",
    "xi jinping", "netanyahu", "modi", "erdogan", "meloni",
    # Geopolitical events
    "war", "ceasefire", "sanction", "invasion", "nato", "un security",
    "treaty", "diplomacy", "annexat", "occupation", "missile", "nuclear",
    "ukraine", "russia", "israel", "gaza", "iran", "north korea", "taiwan",
    # Policy
    "legislation", "bill pass", "impeach", "indict", "convict", "resign",
    "tariff", "trade deal", "g7", "g20",
]

# Resolution clarity thresholds
OUTCOME_YES_THRESHOLD = 0.95   # final prob ≥ this → outcome = True
OUTCOME_NO_THRESHOLD = 0.05    # final prob ≤ this → outcome = False
MIN_PRICE_POINTS = 5           # need at least this many daily price points


def _is_political(market: dict) -> bool:
    """Check if market belongs to political/geopolitical category."""
    # Old markets have explicit categories
    category = (market.get("category") or "").strip().lower()
    if category in POLITICAL_CATEGORIES:
        return True
    # New markets (~2022+) have empty category — use question keyword matching
    question = (market.get("question") or "").lower()
    return any(kw in question for kw in POLITICAL_KEYWORDS)


def _parse_outcome_date(market: dict) -> str | None:
    """Extract resolution date as YYYY-MM-DD string."""
    for field in ("endDate", "resolutionTime", "startDate"):
        val = market.get(field)
        if not val:
            continue
        try:
            # ISO format: "2024-11-05T00:00:00Z" or "2024-11-05"
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return None


def _extract_outcome(market: dict, prices: list[dict]) -> bool | None:
    """
    Determine binary outcome from price history.
    Returns True/False, or None if ambiguous.
    """
    if not prices:
        return None

    # Use the last price point as the resolution probability
    final_prob = prices[-1]["probability"]
    if final_prob >= OUTCOME_YES_THRESHOLD:
        return True
    if final_prob <= OUTCOME_NO_THRESHOLD:
        return False

    # Also check market's resolutionValue field if present
    res_val = (market.get("resolutionValue") or "").strip().lower()
    if res_val in ("yes", "1", "true"):
        return True
    if res_val in ("no", "0", "false"):
        return False

    return None  # ambiguous


def _fetch_price_history(market_id: str, outcome_date: str, client: httpx.Client) -> list[dict]:
    """Fetch and normalise daily prices for a market (synchronous)."""
    try:
        r = client.get(
            f"{GAMMA_BASE}/prices-history",
            params={"market": market_id, "interval": "1d", "fidelity": 1},
            timeout=20,
        )
        if r.status_code != 200:
            return []
        history = r.json().get("history", [])
        outcome_dt = datetime.strptime(outcome_date, "%Y-%m-%d").date()
        by_date: dict[str, float] = {}
        for point in history:
            ts = point.get("t", 0)
            prob = point.get("p")
            if ts and prob is not None:
                dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
                if dt <= outcome_dt:
                    by_date[dt.strftime("%Y-%m-%d")] = round(float(prob), 4)
        return [{"date": d, "probability": v} for d, v in sorted(by_date.items())]
    except Exception as exc:
        logger.debug("Price history error for %s: %s", market_id, exc)
        return []


def harvest(
    data_dir: Path,
    start_date: str = "2023-01-01",
    end_date: str | None = None,
) -> list[dict]:
    """
    Main harvest function. Returns list of harvested event dicts and
    writes data_dir/pm_harvest/events.jsonl.
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    harvest_dir = data_dir / "pm_harvest"
    harvest_dir.mkdir(parents=True, exist_ok=True)
    output_path = harvest_dir / "events.jsonl"

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    console.print(f"[bold cyan]Polymarket Harvest[/bold cyan] — {start_date} → {end_date}")
    console.print(f"Output: {output_path}")

    # Load already-harvested IDs to allow resumption
    seen_ids: set[str] = set()
    existing_events: list[dict] = []
    if output_path.exists():
        with open(output_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    ev = json.loads(line)
                    seen_ids.add(ev["pm_id"])
                    existing_events.append(ev)
        console.print(f"  Resuming — {len(seen_ids)} events already harvested")

    new_events: list[dict] = []
    page = 0
    total_checked = 0
    total_skipped_category = 0
    total_skipped_ambiguous = 0
    total_skipped_sparse = 0

    with httpx.Client(timeout=30) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching pages...", total=None)

            while True:
                raw_cache = harvest_dir / f"raw_page_{page}.json"

                # Load from cache, or fetch and cache
                markets = None
                if raw_cache.exists():
                    try:
                        with open(raw_cache) as f:
                            markets = json.load(f)
                    except (json.JSONDecodeError, ValueError):
                        logger.warning("Corrupted cache page %d — re-fetching", page)
                        raw_cache.unlink()

                if markets is None:
                    try:
                        r = client.get(
                            f"{GAMMA_BASE}/markets",
                            params={
                                "closed": "true",
                                "limit": PAGE_SIZE,
                                "offset": page * PAGE_SIZE,
                            },
                            timeout=20,
                        )
                        if r.status_code != 200:
                            logger.warning("Page %d: HTTP %d", page, r.status_code)
                            break
                        markets = r.json()
                        with open(raw_cache, "w") as f:
                            json.dump(markets, f)
                        time.sleep(REQUEST_DELAY)
                    except Exception as exc:
                        logger.error("Page %d fetch error: %s", page, exc)
                        break

                if not markets:
                    break  # End of pagination

                for market in markets:
                    total_checked += 1
                    market_id = market.get("id") or market.get("conditionId", "")
                    if not market_id or market_id in seen_ids:
                        continue

                    # Date filter
                    outcome_date = _parse_outcome_date(market)
                    if not outcome_date:
                        continue
                    outcome_dt = datetime.strptime(outcome_date, "%Y-%m-%d")
                    if not (start_dt <= outcome_dt <= end_dt):
                        continue

                    # Category filter
                    if not _is_political(market):
                        total_skipped_category += 1
                        continue

                    # Price history
                    prices = _fetch_price_history(market_id, outcome_date, client)
                    if len(prices) < MIN_PRICE_POINTS:
                        total_skipped_sparse += 1
                        continue

                    # Outcome clarity
                    outcome = _extract_outcome(market, prices)
                    if outcome is None:
                        total_skipped_ambiguous += 1
                        continue

                    slug = market.get("slug", "")
                    question = market.get("question") or market.get("title") or market.get("name") or ""
                    if not question:
                        continue

                    # Infer category label
                    category = (market.get("category") or "Politics").strip()

                    event = {
                        "pm_id": market_id,
                        "question": question.strip(),
                        "outcome": outcome,
                        "outcome_date": outcome_date,
                        "category": category,
                        "pm_url": f"https://polymarket.com/event/{slug}" if slug else "",
                        "prices": prices,
                    }

                    seen_ids.add(market_id)
                    new_events.append(event)

                    # Append to output file immediately (crash-safe)
                    with open(output_path, "a") as f:
                        f.write(json.dumps(event) + "\n")

                progress.update(
                    task,
                    description=(
                        f"Page {page} — {len(existing_events) + len(new_events)} events "
                        f"(checked {total_checked}, skipped cat={total_skipped_category} "
                        f"ambig={total_skipped_ambiguous} sparse={total_skipped_sparse})"
                    ),
                )
                page += 1

    all_events = existing_events + new_events
    console.print(f"\n[bold green]Done.[/bold green] Total events: {len(all_events)}")
    console.print(f"  New this run: {len(new_events)}")
    console.print(f"  Skipped — not political: {total_skipped_category}")
    console.print(f"  Skipped — ambiguous outcome: {total_skipped_ambiguous}")
    console.print(f"  Skipped — sparse price history: {total_skipped_sparse}")

    return all_events


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="Harvest Polymarket political events")
    parser.add_argument("--data-dir", default="data/poc", help="Base data directory (default: data/poc)")
    parser.add_argument("--start", default="2023-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    import os
    base = Path(os.environ.get("DATA_DIR", args.data_dir))
    harvest(base, start_date=args.start, end_date=args.end)
