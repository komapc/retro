"""
One-time script: use LLM to generate better search keywords for all event files.
Run: DATA_DIR=/path/to/data uv run --project /path/to/pipeline python scripts/improve_keywords.py
"""

import asyncio
import json
import os
from pathlib import Path

import litellm
from rich.console import Console

console = Console()

ISRAEL_RELATED_CATEGORIES = {"A", "B", "C", "D", "F"}  # add Hebrew for these
# G (tech/global), E (global) — Hebrew only if Israeli angle is strong

SYSTEM = """\
You are a search keyword specialist for a news archive retrieval system.
Given a past event, generate search keywords to find news articles published
BEFORE the event occurred — articles that were predicting, anticipating, or
discussing the likelihood of this event.

Rules:
- Keywords should reflect what journalists were writing about in the LEAD-UP period
- For Israeli/Middle East events: include 2-3 Hebrew keywords + 2-3 English keywords
- For global events with no Israeli angle: English only (3-4 keywords)
- Each keyword should be 2-5 words, no quotes, no operators
- Order: most specific first (named actors, locations), then broader topic keywords
- Do NOT include the outcome itself as a keyword (e.g. don't use "ceasefire signed" if the event is a ceasefire)
- Use terms that would appear in articles BEFORE the event, e.g. "ceasefire negotiations" not "ceasefire reached"

Return a JSON object with one field: "search_keywords" (array of strings).
"""

def needs_hebrew(event_id: str) -> bool:
    cat = event_id[0]
    if cat in ISRAEL_RELATED_CATEGORIES:
        return True
    # G/E: some have Israeli angle
    return False


async def generate_keywords(event: dict) -> list[str]:
    has_hebrew = needs_hebrew(event["id"])
    hebrew_instruction = (
        "Include 2-3 Hebrew keywords first, then 2-3 English keywords."
        if has_hebrew
        else "English keywords only (3-5 total)."
    )

    prompt = f"""\
Event ID: {event["id"]}
Event name: {event["name"]}
Outcome date: {event["outcome_date"]}
Predictive window: {event.get("predictive_window_days", 14)} days before the event
Did it happen: {event.get("outcome", True)}

{hebrew_instruction}

Generate search keywords to find news articles written in the {event.get("predictive_window_days", 14)} days
BEFORE {event["outcome_date"]} that were anticipating or predicting this event.

Return JSON: {{"search_keywords": ["kw1", "kw2", ...]}}"""

    response = await litellm.acompletion(
        model="openrouter/google/gemini-2.0-flash-001",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
        response_format={"type": "json_object"},
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    )

    content = response.choices[0].message.content
    data = json.loads(content)
    return data.get("search_keywords", [])


async def main():
    from sys import argv
    data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
    events_dir = data_dir / "events"
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]OPENROUTER_API_KEY not set[/red]")
        return

    event_files = sorted(events_dir.glob("*.json"))
    console.print(f"[bold]Improving keywords for {len(event_files)} events...[/bold]\n")

    for ef in event_files:
        event = json.loads(ef.read_text())
        old_kws = event.get("search_keywords", [])

        try:
            new_kws = await generate_keywords(event)
            event["search_keywords"] = new_kws
            ef.write_text(json.dumps(event, indent=2, ensure_ascii=False))

            old_str = f"[dim]{len(old_kws)} kws[/dim]"
            new_str = f"[green]{len(new_kws)} kws[/green]"
            console.print(f"  {event['id']:4s}  {old_str} → {new_str}  {event['name'][:50]}")
            for kw in new_kws:
                console.print(f"        [dim]· {kw}[/dim]")

        except Exception as e:
            console.print(f"  [red]{event['id']}  ERROR: {e}[/red]")

        await asyncio.sleep(0.3)

    console.print("\n[bold green]Done.[/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
