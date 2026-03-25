import json as _json
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from enum import Enum


# --- LLM Output Schemas ---

class GatekeeperOutput(BaseModel):
    is_prediction: bool
    reason: str
    prediction_count_estimate: int = Field(default=0, ge=0)


class PredictionType(str, Enum):
    binary = "binary"
    continuous = "continuous"
    range = "range"
    trend = "trend"


class PredictionExtraction(BaseModel):
    quote: str = Field(description="Exact sentence(s) from the article containing the prediction")
    claim: str = Field(description="One-sentence neutral summary in English")
    stance: float = Field(ge=-1.0, le=1.0, description="Directional outlook: -1=bearish, +1=bullish")
    sentiment: float = Field(ge=0.0, le=1.0, description="Emotional tone: 0=cold, 1=highly charged")
    certainty: float = Field(ge=0.0, le=1.0, description="Linguistic confidence: 0=very hedged, 1=absolute")
    specificity: float = Field(ge=0.0, le=1.0, description="Concreteness and falsifiability: 0=vague, 1=precise")
    hedge_ratio: float = Field(ge=0.0, le=1.0, description="Density of hedging language (might/could/possibly)")
    conditionality: float = Field(ge=0.0, le=1.0, description="0=unconditional, 1=fully conditional (only if X then Y)")
    magnitude: float = Field(ge=0.0, le=1.0, description="Extremity of predicted outcome: 0=minor, 1=historic")
    time_horizon: str = Field(description="days/weeks/months/years/unspecified")
    time_horizon_days: Optional[int] = Field(default=None, description="Best estimate in days, null if unspecified")
    prediction_type: PredictionType
    source_authority: float = Field(ge=0.0, le=1.0, description="0=personal opinion, 1=named insider sources")


class ExtractionOutput(BaseModel):
    predictions: list[PredictionExtraction]

    @model_validator(mode="before")
    @classmethod
    def _deserialize_string_predictions(cls, data: Any) -> Any:
        """
        Some models (in TOOLS mode) double-serialize nested objects as strings.
        Handles two observed variants:
          1. Valid JSON strings:   '{"quote": "...", ...}'
          2. YAML-style strings:   'quote: ... source_authority: 0.8'
        """
        if isinstance(data, dict) and "predictions" in data:
            preds = data["predictions"]
            if not isinstance(preds, list):
                return data
            parsed = []
            for p in preds:
                if not isinstance(p, str):
                    parsed.append(p)
                    continue
                # Try JSON first
                try:
                    parsed.append(_json.loads(p))
                    continue
                except _json.JSONDecodeError:
                    pass
                # Try YAML-style "key: value" lines
                try:
                    import yaml as _yaml
                    obj = _yaml.safe_load(p)
                    if isinstance(obj, dict):
                        parsed.append(obj)
                        continue
                except Exception:
                    pass
                # Give up — keep as-is and let Pydantic report the error
                parsed.append(p)
            data["predictions"] = parsed
        return data


class CellSignal(BaseModel):
    """
    Aggregated signal for one (event, source) cell.
    Computed from all predictions across all articles for the cell.
    Continuous metrics are weighted mean (weight = certainty × specificity).
    Categorical fields use majority vote. Median for time_horizon_days.
    """
    claim_count:      int
    stance:           float
    sentiment:        float
    certainty:        float
    specificity:      float
    hedge_ratio:      float
    conditionality:   float
    magnitude:        float
    source_authority: float
    time_horizon:     str
    time_horizon_days: Optional[int]
    prediction_type:  str
    quotes:           list[str]
    claims:           list[str]


# --- Matrix Progress Tracking ---

class CellStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    failed = "failed"
    no_predictions = "no_predictions"


# Visual representation per status
CELL_CHAR: dict[CellStatus, str] = {
    CellStatus.pending: "░",
    CellStatus.in_progress: "▒",
    CellStatus.done: "▓",
    CellStatus.failed: "✗",
    CellStatus.no_predictions: "·",
}

CELL_COLOR: dict[CellStatus, str] = {
    CellStatus.pending: "white",
    CellStatus.in_progress: "yellow",
    CellStatus.done: "green",
    CellStatus.failed: "red",
    CellStatus.no_predictions: "bright_black",
}


class MatrixCell(BaseModel):
    event_id: str
    source_id: str
    status: CellStatus = CellStatus.pending
    prediction_count: int = 0
    error: Optional[str] = None


class MatrixState(BaseModel):
    cells: dict[str, MatrixCell] = {}  # key: "event_id:source_id"

    def key(self, event_id: str, source_id: str) -> str:
        return f"{event_id}:{source_id}"

    def get(self, event_id: str, source_id: str) -> MatrixCell:
        k = self.key(event_id, source_id)
        if k not in self.cells:
            self.cells[k] = MatrixCell(event_id=event_id, source_id=source_id)
        return self.cells[k]

    def set_status(self, event_id: str, source_id: str, status: CellStatus, **kwargs) -> None:
        cell = self.get(event_id, source_id)
        cell.status = status
        for k, v in kwargs.items():
            setattr(cell, k, v)

    def stats(self) -> dict[str, int]:
        counts: dict[str, int] = {s.value: 0 for s in CellStatus}
        for cell in self.cells.values():
            counts[cell.status.value] += 1
        return counts
