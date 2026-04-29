"""
Pipeline runner: orchestrates gatekeeper → extraction for one article.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from rich.console import Console

from .gatekeeper import check_is_prediction
from .extractor import extract_predictions
from .models import ExtractionOutput, CellStatus
from .progress import update_cell

console = Console()


@dataclass
class ArticleInput:
    text: str
    source_id: str
    source_name: str
    article_date: str
    event_id: str
    event_name: str
    event_description: str
    journalist: Optional[str] = None
    article_url: Optional[str] = None


@dataclass
class PipelineResult:
    article: ArticleInput
    is_prediction: bool
    gatekeeper_reason: str
    extraction: Optional[ExtractionOutput] = None
    error: Optional[str] = None


async def run_article(article: ArticleInput) -> PipelineResult:
    update_cell(article.event_id, article.source_id, CellStatus.in_progress)

    try:
        # Stage 1: Gatekeeper
        gate, _ = await check_is_prediction(
            article_text=article.text,
            source_name=article.source_name,
            article_date=article.article_date,
            event_name=article.event_name,
        )

        if not gate.is_prediction:
            update_cell(article.event_id, article.source_id, CellStatus.no_predictions)
            return PipelineResult(
                article=article,
                is_prediction=False,
                gatekeeper_reason=gate.reason,
            )

        # Stage 2: Extraction
        extraction, _ = await extract_predictions(
            article_text=article.text,
            source_name=article.source_name,
            article_date=article.article_date,
            event_name=article.event_name,
            event_description=article.event_description,
            journalist=article.journalist or "unknown",
        )

        update_cell(
            article.event_id,
            article.source_id,
            CellStatus.done,
            prediction_count=len(extraction.predictions),
        )

        return PipelineResult(
            article=article,
            is_prediction=True,
            gatekeeper_reason=gate.reason,
            extraction=extraction,
        )

    except Exception as e:
        error_msg = str(e)
        update_cell(article.event_id, article.source_id, CellStatus.failed, error=error_msg)
        return PipelineResult(
            article=article,
            is_prediction=False,
            gatekeeper_reason="",
            error=error_msg,
        )
