"""
Core forecast logic — Phase 2: live pipeline integration.

Flow:
  1. search_articles(question) — Serper.dev → Brave → DDG fallback
  2. For each article (in parallel): gatekeeper → extractor
  3. Weight each source by credibility from leaderboard
  4. Aggregate: weighted mean stance + 95% CI → return ForecastResponse
"""
import asyncio
import logging
import math
import re
from datetime import datetime
from urllib.parse import urlparse

from tm.gatekeeper import check_is_prediction
from tm.extractor import extract_predictions
from tm.web_search import search_articles, SearchResult

from .leaderboard import get_credibility_weight
from .models import ForecastRequest, ForecastResponse, SourceSignal
from .config import settings

logger = logging.getLogger(__name__)

# Domain → leaderboard source_id mapping
_DOMAIN_MAP: dict[str, str] = {
    "timesofisrael.com": "toi",
    "haaretz.com": "haaretz",
    "jpost.com": "jpost",
    "ynetnews.com": "ynet",
    "ynet.co.il": "ynet",
    "israelhayom.com": "israel_hayom",
    "israelhayom.co.il": "israel_hayom",
    "globes.co.il": "globes",
    "en.globes.co.il": "globes",
    "maariv.co.il": "maariv",
    "calcalist.co.il": "calcalist",
    "walla.co.il": "walla",
    "news.walla.co.il": "walla",
    "mako.co.il": "mako",
    "kan.org.il": "kan",
    "13tv.co.il": "channel13",
    "reuters.com": "reuters",
    "bbc.com": "bbc",
    "aljazeera.com": "aljazeera",
    "cnn.com": "cnn",
    "bloomberg.com": "bloomberg",
    "wsj.com": "wsj",
    "ft.com": "ft",
    "apnews.com": "ap",
}


def _source_id_from_url(url: str) -> str:
    domain = re.sub(r"^www\.", "", urlparse(url).netloc)
    for key, sid in _DOMAIN_MAP.items():
        if domain == key or domain.endswith("." + key):
            return sid
    return domain  # fallback: raw domain as id


async def _process_article(
    result: SearchResult,
    question: str,
) -> tuple[SearchResult, list] | None:
    """
    Run gatekeeper + extractor for one article.
    Returns (result, predictions) or None if article not relevant/predictive.
    Calls gatekeeper and extractor directly (not run_article) to avoid
    writing to progress.json which belongs to the batch pipeline.
    """
    text = result.snippet
    if not text or len(text) < 40:
        return None

    source_name = result.source or _source_id_from_url(result.url)
    article_date = result.published_date or datetime.now().strftime("%Y-%m-%d")

    try:
        gate = await check_is_prediction(
            article_text=text,
            source_name=source_name,
            article_date=article_date,
            event_name=question,
        )
    except Exception as exc:
        logger.warning("Gatekeeper failed for %s: %s", result.url, exc)
        return None

    if not gate.is_prediction:
        logger.debug("Gatekeeper rejected: %s", result.url)
        return None

    try:
        extraction = await extract_predictions(
            article_text=text,
            source_name=source_name,
            article_date=article_date,
            event_name=question,
            event_description=question,
        )
    except Exception as exc:
        logger.warning("Extractor failed for %s: %s", result.url, exc)
        return None

    if not extraction.predictions:
        return None

    return (result, extraction.predictions)


async def run_forecast(req: ForecastRequest) -> ForecastResponse:
    limit = req.max_articles or settings.max_articles

    # Step 1: search
    try:
        search_results: list[SearchResult] = await asyncio.to_thread(
            search_articles, req.question, limit
        )
    except Exception as exc:
        logger.error("Search failed: %s", exc)
        search_results = []

    if not search_results:
        logger.warning("No articles found for: %s", req.question[:80])
        return _empty_response(req.question)

    logger.info("Found %d articles for: %s", len(search_results), req.question[:80])

    # Step 2: gatekeeper + extractor in parallel
    outcomes = await asyncio.gather(
        *[_process_article(r, req.question) for r in search_results],
        return_exceptions=True,
    )

    # Step 3: build per-source signals
    source_signals: list[SourceSignal] = []
    all_stances: list[float] = []
    all_weights: list[float] = []

    for result, outcome in zip(search_results, outcomes):
        if isinstance(outcome, Exception) or outcome is None:
            continue
        _, predictions = outcome

        source_id = _source_id_from_url(result.url)
        credibility = get_credibility_weight(source_id)
        avg_stance = sum(p.stance for p in predictions) / len(predictions)
        avg_certainty = sum(p.certainty for p in predictions) / len(predictions)
        weight = credibility * avg_certainty

        all_stances.append(avg_stance)
        all_weights.append(weight)

        source_signals.append(SourceSignal(
            source_id=source_id,
            source_name=result.source or source_id,
            url=result.url,
            stance=round(avg_stance, 3),
            certainty=round(avg_certainty, 3),
            credibility_weight=round(credibility, 3),
            claims=[p.claim for p in predictions if p.claim],
        ))

    if not all_stances:
        logger.warning("No usable predictions extracted from %d articles", len(search_results))
        return _empty_response(req.question)

    # Step 4: weighted mean + 95% CI
    total_w = sum(all_weights)
    mean = sum(s * w for s, w in zip(all_stances, all_weights)) / total_w
    variance = sum(w * (s - mean) ** 2 for s, w in zip(all_stances, all_weights)) / total_w
    std = math.sqrt(variance)
    n = len(all_stances)
    sem = std / math.sqrt(n) if n > 1 else std
    ci_low = max(-1.0, mean - 1.96 * sem)
    ci_high = min(1.0, mean + 1.96 * sem)

    logger.info(
        "Forecast: mean=%.3f std=%.3f ci=[%.3f,%.3f] articles=%d",
        mean, std, ci_low, ci_high, n,
    )

    return ForecastResponse(
        question=req.question,
        mean=round(mean, 4),
        std=round(std, 4),
        ci_low=round(ci_low, 4),
        ci_high=round(ci_high, 4),
        articles_used=n,
        sources=source_signals,
        placeholder=False,
    )


def _empty_response(question: str) -> ForecastResponse:
    """Return a maximally uncertain response when no usable articles are found."""
    return ForecastResponse(
        question=question,
        mean=0.0,
        std=0.0,
        ci_low=-0.2,
        ci_high=0.2,
        articles_used=0,
        sources=[],
        placeholder=False,
    )
