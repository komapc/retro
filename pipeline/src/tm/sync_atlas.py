import json
import re
from pathlib import Path
from typing import List, Dict

def parse_events(events_md: str) -> List[Dict]:
    events = []
    # Regex to capture table rows with metadata
    pattern = re.compile(r"\| ([A-G]\d+) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|")
    for line in events_md.splitlines():
        match = pattern.search(line)
        if match:
            eid, name, outcome, date, keywords, criteria = match.groups()
            if eid and name.strip() != "Event":
                events.append({
                    "id": eid.strip(),
                    "name": name.strip(),
                    "outcome": outcome.strip() == "True",
                    "outcome_date": date.strip(),
                    "search_keywords": [k.strip().strip('"') for k in keywords.split(",")],
                    "llm_referee_criteria": criteria.strip()
                })
    return events

def main():
    root = Path(__file__).parent.parent.parent.parent
    events_file = root / "TruthMachine" / "EVENTS.md"
    sources_file = root / "TruthMachine" / "sources.json"
    atlas_dir = root / "data" / "atlas"
    events_dir = root / "data" / "events"
    sources_dir = root / "data" / "sources"

    # Load sources
    with open(sources_file, "r") as f:
        sources_data = json.load(f)
    
    # Load and parse events
    with open(events_file, "r") as f:
        events_md = f.read()
    events = parse_events(events_md)

    # Ensure directories exist
    for d in [atlas_dir, events_dir, sources_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Save individual source files
    for source in sources_data["sources"]:
        with open(sources_dir / f"{source['id']}.json", "w") as f:
            json.dump(source, f, indent=2)

    # Save individual event files and create atlas structure
    for event in events:
        eid = event["id"]
        with open(events_dir / f"{eid}.json", "w") as f:
            json.dump(event, f, indent=2)
        
        # Create atlas/event_id/source_id structure
        for source in sources_data["sources"]:
            sid = source["id"]
            (atlas_dir / eid / sid).mkdir(parents=True, exist_ok=True)

    print(f"Initialized Factum Atlas: {len(events)} events, {len(sources_data['sources'])} sources.")

if __name__ == "__main__":
    main()
