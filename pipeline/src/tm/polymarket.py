"""
Polymarket historical data fetcher.

Searches the Gamma API for a market matching each event's keywords,
then fetches a daily price history and caches it to
  data/polymarket/{event_id}.json

Schema of cached file:
{
  "event_id": "C05",
  "market_id": "...",
  "question": "...",
  "market_url": "https://polymarket.com/event/...",
  "outcome_prob": 0.83,          # final resolution probability
  "prices": [                    # sorted oldest → newest
    {"date": "2024-04-07", "probability": 0.12},
    ...
  ]
}

If no market is found the file is written with prices: [] so callers
can distinguish "not found" (missing file) from "found but empty".
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console

console = Console()

GAMMA_BASE = "https://gamma-api.polymarket.com"


async def _search_market(keywords: list[str], event_name: str) -> Optional[dict]:
    """Return the best-matching Gamma market dict, or None."""
    # Try the most specific keyword first, then fall back to the event name
    queries = [kw for kw in keywords if kw and not kw.startswith('"')] + [event_name]
    # Also try quoted keywords stripped of quotes
    queries += [kw.strip('"') for kw in keywords if kw.startswith('"')]

    async with httpx.AsyncClient(timeout=15) as client:
        for q in queries[:4]:  # max 4 attempts per event
            try:
                r = await client.get(
                    f"{GAMMA_BASE}/markets",
                    params={"search": q, "limit": 5, "active": "false"},
                )
                if r.status_code != 200:
                    continue
                markets = r.json()
                if markets:
                    return markets[0]
            except Exception:
                continue
    return None


async def _fetch_price_history(market_id: str, outcome_date: str) -> list[dict]:
    """
    Fetch daily closing prices for a market from Gamma API.
    Returns [{date, probability}] sorted oldest→newest.
    """
    try:
        # Gamma prices-history endpoint
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"{GAMMA_BASE}/prices-history",
                params={"market": market_id, "interval": "1d", "fidelity": 1},
            )
            if r.status_code != 200:
                return []
            data = r.json()
            # Response is {"history": [{"t": timestamp_ms, "p": probability}, ...]}
            history = data.get("history", [])
            prices = []
            outcome_dt = datetime.strptime(outcome_date, "%Y-%m-%d")
            for point in history:
                ts = point.get("t", 0)
                prob = point.get("p")
                if ts and prob is not None:
                    dt = datetime.fromtimestamp(ts / 1000)
                    # Only keep data up to outcome date
                    if dt.date() <= outcome_dt.date():
                        prices.append({
                            "date": dt.strftime("%Y-%m-%d"),
                            "probability": round(float(prob), 4),
                        })
            # Deduplicate by date (keep last entry per day)
            by_date: dict[str, float] = {}
            for p in prices:
                by_date[p["date"]] = p["probability"]
            return [{"date": d, "probability": v} for d, v in sorted(by_date.items())]
    except Exception as e:
        console.print(f"    [dim red]Price history error: {e}[/dim red]")
        return []


async def fetch_event_prices(event: dict, cache_dir: Path) -> list[dict]:
    """
    Main entry point. Returns price series for an event, using cache if available.
    Writes/reads from cache_dir/{event_id}.json.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{event['id']}.json"

    if cache_path.exists():
        with open(cache_path) as f:
            cached = json.load(f)
        return cached.get("prices", [])

    console.print(f"  [dim cyan]Polymarket search: {event['name']}[/dim cyan]")

    keywords = event.get("search_keywords", [])
    market = await _search_market(keywords, event["name"])

    if not market:
        console.print(f"  [dim]No Polymarket market found for {event['id']}[/dim]")
        # Cache negative result so we don't re-query
        with open(cache_path, "w") as f:
            json.dump({"event_id": event["id"], "market_id": None, "prices": []}, f)
        return []

    market_id = market.get("id") or market.get("conditionId", "")
    question = market.get("question", "")
    slug = market.get("slug", "")
    market_url = f"https://polymarket.com/event/{slug}" if slug else ""

    console.print(f"  [dim green]Found: {question[:60]}[/dim green]")

    prices = await _fetch_price_history(market_id, event["outcome_date"])

    result = {
        "event_id": event["id"],
        "market_id": market_id,
        "question": question,
        "market_url": market_url,
        "prices": prices,
    }
    with open(cache_path, "w") as f:
        json.dump(result, f, indent=2)

    return prices


async def prefetch_all(events_dir: Path, cache_dir: Path, event_ids: list[str]):
    """Fetch Polymarket data for all given event IDs concurrently."""
    tasks = []
    events = []
    for eid in event_ids:
        p = events_dir / f"{eid}.json"
        if p.exists():
            with open(p) as f:
                events.append(json.load(f))

    results = await asyncio.gather(
        *[fetch_event_prices(ev, cache_dir) for ev in events],
        return_exceptions=True,
    )
    found = sum(1 for r in results if isinstance(r, list) and r)
    console.print(f"[bold]Polymarket:[/bold] found price data for {found}/{len(events)} events")


if __name__ == "__main__":
    import os, sys
    data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
    event_ids = sys.argv[1:] if len(sys.argv) > 1 else []
    if not event_ids:
        event_ids = [p.stem for p in sorted((data_dir / "events").glob("*.json"))]
    asyncio.run(prefetch_all(data_dir / "events", data_dir / "polymarket", event_ids))
