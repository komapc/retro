import asyncio
import json
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from enum import Enum

from rich.console import Console
from .models import CellStatus, ExtractionOutput
from .runner import run_article, ArticleInput
from .progress import update_cell, load_state
from .ingestor import BraveIngestor, GDELTIngestor, DDGIngestor
import httpx
from bs4 import BeautifulSoup

console = Console()

class SearchMode(str, Enum):
    mock = "mock"
    local_file = "local_file"
    api = "api"

class Orchestrator:
    def __init__(self, data_dir: Path, mode: SearchMode = SearchMode.mock):
        self.data_dir = data_dir
        self.mode = mode
        from .config import settings
        _vault_default = str(settings.vault_dir) if settings.vault_dir != Path("") else str(data_dir / "vault2")
        self.vault_dir = Path(os.environ.get("VAULT_DIR", _vault_default))
        self.atlas_dir = data_dir / "atlas"
        self.events_dir = data_dir / "events"
        self.sources_dir = data_dir / "sources"
        self.raw_ingest_dir = data_dir / "raw_ingest"
        
        for d in [self.vault_dir / "articles", self.vault_dir / "extractions", self.raw_ingest_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # DDG is the default free ingestor; Brave used if key present
        brave_key = os.environ.get("BRAVE_API_KEY", settings.brave_api_key)
        self.ingestor = BraveIngestor(brave_key) if brave_key else DDGIngestor()
        self.ddg = DDGIngestor()  # always available as fallback

    def get_article_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def get_full_text(self, url: str) -> str:
        console.print(f"    [dim]Scraping full text from: {url}[/dim]")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, follow_redirects=True)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    for s in soup(["script", "style", "nav", "footer", "header"]):
                        s.extract()
                    return soup.get_text(separator=" ", strip=True)
        except Exception as e:
            console.print(f"    [dim red]Scrape failed: {str(e)}[/dim red]")
        return ""

    async def run_event(self, event_id: str):
        event_path = self.events_dir / f"{event_id}.json"
        if not event_path.exists():
            return
        
        with open(event_path, "r") as f:
            event = json.load(f)
        
        outcome_date = datetime.strptime(event["outcome_date"], "%Y-%m-%d")
        window_days = event.get("predictive_window_days", 14)
        start_date = outcome_date - timedelta(days=window_days)
        
        console.print(f"[bold cyan]Processing Event:[/bold cyan] {event['name']} ({event_id})")

        source_files = sorted(list(self.sources_dir.glob("*.json")))
        for source_file in source_files:
            with open(source_file, "r") as f:
                source = json.load(f)
            
            if source["id"] not in ["ynet", "haaretz", "toi", "globes", "reuters", "jpost"]:
                continue

            state = load_state()
            cell = state.get(event_id, source["id"])
            if cell.status == CellStatus.done:
                continue

            console.print(f"  [bold]Source:[/bold] {source['name']}")
            
            articles = await self.search_articles(source, event, start_date, outcome_date)
            
            if not articles:
                update_cell(event_id, source["id"], CellStatus.no_predictions)
                continue

            for raw_art in articles:
                await self.process_article(raw_art, event, source)

    async def search_articles(self, source: dict, event: dict, start: datetime, end: datetime) -> List[dict]:
        if self.mode == SearchMode.local_file:
            return self.local_file_search(source["id"], event["id"])
        
        if self.mode == SearchMode.api:
            domain = (
                source["url"]
                .replace("https://www.", "")
                .replace("http://www.", "")
                .replace("https://", "")
                .replace("http://", "")
                .split("/")[0]
            )
            if isinstance(self.ingestor, BraveIngestor):
                results = await self.ingestor.search(domain, event["search_keywords"], start, end)
                if not results:
                    console.print(f"    [dim]Brave empty → DDG fallback[/dim]")
                    results = await self.ddg.search(domain, event["search_keywords"], start, end)
            else:
                results = await self.ddg.search(domain, event["search_keywords"], start, end)

            results = results[:5]
            for res in results:
                if res.get("url"):
                    full_text = await self.get_full_text(res["url"])
                    if len(full_text) > 200:
                        res["text"] = full_text
            return [r for r in results if len(r.get("text", "")) > 200]
            
        return []

    def local_file_search(self, source_id: str, event_id: str) -> List[dict]:
        articles = []
        search_path = self.raw_ingest_dir / source_id / event_id
        if search_path.exists():
            for art_file in search_path.glob("*.json"):
                with open(art_file, "r") as f:
                    articles.append(json.load(f))
        return articles

    async def process_article(self, raw_art: dict, event: dict, source: dict):
        text = raw_art["text"]
        art_hash = self.get_article_hash(text)
        
        vault_path = self.vault_dir / "articles" / f"{art_hash}.json"
        if not vault_path.exists():
            with open(vault_path, "w") as f:
                json.dump(raw_art, f, indent=2)
        
        model_v = "v1" 
        extract_path = self.vault_dir / "extractions" / f"{art_hash}_{event['id']}_{model_v}.json"
        
        if extract_path.exists():
            self.create_atlas_link(event["id"], source["id"], art_hash, extract_path, raw_art, event.get("outcome_date", ""))
            return

        article_input = ArticleInput(
            text=text,
            source_id=source["id"],
            source_name=source["name"],
            article_date=raw_art["published_at"],
            event_id=event["id"],
            event_name=event["name"],
            event_description=event.get("llm_referee_criteria", ""),
            journalist=raw_art.get("author"),
            article_url=raw_art.get("url")
        )
        
        result = await run_article(article_input)

        if result.error:
            console.print(f"    [bold red]Runner Error:[/bold red] {result.error}")
        
        if result.extraction:
            console.print(f"    [green]Success![/green] Extracted {len(result.extraction.predictions)} predictions.")
            try:
                with open(extract_path, "w") as f:
                    data = {
                        "extraction": result.extraction.model_dump(),
                        "prompt_version": model_v,
                        "run_date": datetime.now().isoformat()
                    }
                    json.dump(data, f, indent=2)
                console.print(f"    [dim]Saved to vault: {extract_path}[/dim]")
                self.create_atlas_link(event["id"], source["id"], art_hash, extract_path, raw_art, event.get("outcome_date", ""))
            except Exception as e:
                console.print(f"    [bold red]Failed to save to vault:[/bold red] {str(e)}")
        else:
            console.print(f"    [yellow]Extraction resulted in 0 predictions.[/yellow]")

    def create_atlas_link(self, eid: str, sid: str, art_hash: str, extract_path: Path, raw_art: dict, event_date: str = ""):
        link_dir = self.atlas_dir / eid / sid
        link_dir.mkdir(parents=True, exist_ok=True)
        link_path = link_dir / f"entry_{art_hash[:8]}.json"
        with open(extract_path, "r") as f:
            ext_data = json.load(f)

        link_data = {
            "article_hash": art_hash,
            "extraction_id": f"{art_hash}_{eid}_v1",
            "headline": raw_art.get("headline", "N/A"),
            "article_date": raw_art["published_at"],
            "event_date": event_date,
            "predictions": ext_data["extraction"].get("predictions", []),
        }
        with open(link_path, "w") as f:
            json.dump(link_data, f, indent=2)

async def main():
    import sys
    mode = SearchMode.mock
    if len(sys.argv) > 1:
        mode = SearchMode(sys.argv[1])

    console.print(f"[bold green]Starting TruthMachine Orchestrator in {mode.value} mode...[/bold green]")
    data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
    orch = Orchestrator(data_dir, mode=mode)

    # 25 events with likely Polymarket coverage across all domains
    events = [
        "C05", "C06", "C07", "C08", "C09",          # Iran / Regional
        "B04", "B08", "B09", "B10", "B11", "B13",   # Gaza
        "A04", "A12", "A13", "A14", "A15", "A19",   # Israeli Politics
        "D02", "D03",                                 # Economy
        "E07", "E08",                                 # Global
        "G02", "G05", "G06",                         # Tech / AI
        "F05",                                        # Society
    ]

    for eid in events:
        await orch.run_event(eid)


if __name__ == "__main__":
    asyncio.run(main())
