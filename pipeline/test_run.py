import asyncio
import json
from pathlib import Path
from tm.runner import run_article, ArticleInput
from rich import print

async def test():
    sample_path = Path(__file__).parent / "tests" / "sample_article_a10.json"
    with open(sample_path, "r") as f:
        data = json.load(f)
    
    article = ArticleInput(
        text=data["text"],
        source_id=data["source_id"],
        source_name=data["source_name"],
        article_date=data["article_date"],
        event_id=data["event_id"],
        event_name=data["event_name"],
        event_description=data["event_description"],
        journalist=data.get("journalist"),
        article_url=data.get("article_url")
    )
    
    print(f"[bold cyan]Running pipeline for event {article.event_id} and source {article.source_id}...[/bold cyan]")
    result = await run_article(article)
    
    if result.error:
        print(f"[bold red]Error:[/bold red] {result.error}")
    else:
        print(f"Is Prediction: {result.is_prediction}")
        print(f"Reason: {result.gatekeeper_reason}")
        if result.extraction:
            print(f"Predictions Found: {len(result.extraction.predictions)}")
            for i, pred in enumerate(result.extraction.predictions):
                print(f"\n[bold]Prediction {i+1}:[/bold]")
                print(pred.model_dump())

if __name__ == "__main__":
    asyncio.run(test())
