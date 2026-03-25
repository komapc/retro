"""
Aggregate a list of PredictionExtraction objects into a single CellSignal.

Weight for continuous metrics: certainty × specificity.
If all weights are zero, falls back to simple mean.
Categorical fields (time_horizon, prediction_type) use majority vote.
time_horizon_days uses weighted median.
"""

from statistics import median
from collections import Counter
from typing import Optional

from .models import PredictionExtraction, CellSignal


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    total = sum(weights)
    if total == 0:
        return sum(values) / len(values)
    return sum(v * w for v, w in zip(values, weights)) / total


def _majority(values: list[str]) -> str:
    return Counter(values).most_common(1)[0][0]


def _weighted_median(values: list[Optional[int]], weights: list[float]) -> Optional[int]:
    pairs = [(v, w) for v, w in zip(values, weights) if v is not None]
    if not pairs:
        return None
    pairs.sort(key=lambda x: x[0])
    total = sum(w for _, w in pairs)
    if total == 0:
        return int(median(v for v, _ in pairs))
    cumulative = 0.0
    for v, w in pairs:
        cumulative += w
        if cumulative >= total / 2:
            return v
    return pairs[-1][0]


def aggregate_predictions(predictions: list[PredictionExtraction]) -> CellSignal:
    if not predictions:
        raise ValueError("Cannot aggregate empty prediction list")

    weights = [p.certainty * p.specificity for p in predictions]

    def wmean(attr: str) -> float:
        return _weighted_mean([getattr(p, attr) for p in predictions], weights)

    return CellSignal(
        claim_count=len(predictions),
        stance=wmean("stance"),
        sentiment=wmean("sentiment"),
        certainty=wmean("certainty"),
        specificity=wmean("specificity"),
        hedge_ratio=wmean("hedge_ratio"),
        conditionality=wmean("conditionality"),
        magnitude=wmean("magnitude"),
        source_authority=wmean("source_authority"),
        time_horizon=_majority([p.time_horizon for p in predictions]),
        time_horizon_days=_weighted_median(
            [p.time_horizon_days for p in predictions], weights
        ),
        prediction_type=_majority([p.prediction_type for p in predictions]),
        quotes=[p.quote for p in predictions],
        claims=[p.claim for p in predictions],
    )
