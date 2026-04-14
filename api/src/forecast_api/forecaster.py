"""
Core forecast logic.

Phase 1 (current): Placeholder — returns a stub response so the API is
callable end-to-end while the pipeline integration is being wired up.

Phase 2 (TODO): Wire up web_search → gatekeeper → extractor → aggregation.
"""
import logging

from .models import ForecastRequest, ForecastResponse, SourceSignal

logger = logging.getLogger(__name__)


async def run_forecast(req: ForecastRequest) -> ForecastResponse:
    """
    Given a binary question, return a calibrated probability distribution.

    TODO Phase 2 — replace this stub with:
        1. search_articles(req.question, limit) from tm.web_search
        2. For each article: gatekeeper.check_is_prediction() → extractor.extract_predictions()
        3. Weight each source by leaderboard.get_credibility_weight(source_id)
        4. Aggregate: weighted mean + std + 95% CI
    """
    logger.info("Forecast request (placeholder): %s", req.question[:80])

    # --- PLACEHOLDER RESPONSE ---
    # Returns deterministic stub data so the API contract can be tested
    # end-to-end before the pipeline is wired up.
    return ForecastResponse(
        question=req.question,
        mean=0.0,
        std=0.0,
        ci_low=0.0,
        ci_high=0.0,
        articles_used=0,
        sources=[
            SourceSignal(
                source_id="placeholder",
                source_name="Placeholder Source",
                url="https://example.com",
                stance=0.0,
                certainty=0.0,
                credibility_weight=1.0,
                claims=["Pipeline not yet wired — this is a stub response"],
            )
        ],
        placeholder=True,
    )
