from typing import Optional
from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500, description="Binary question to forecast")
    max_articles: Optional[int] = Field(default=None, ge=1, le=20)


class SourceSignal(BaseModel):
    source_id: str
    source_name: str
    url: str
    stance: float = Field(description="Extracted stance [-1, 1]")
    certainty: float = Field(description="Author certainty [0, 1]")
    credibility_weight: float = Field(description="Source trust from leaderboard [0, ∞], 1.0 = neutral")
    claims: list[str] = Field(description="Extracted claim summaries")


class ForecastResponse(BaseModel):
    question: str
    mean: float = Field(description="Credibility-weighted mean stance [-1, 1]. Convert to probability: (mean + 1) / 2")
    std: float = Field(description="Weighted standard deviation")
    ci_low: float = Field(description="95% confidence interval lower bound")
    ci_high: float = Field(description="95% confidence interval upper bound")
    articles_used: int
    sources: list[SourceSignal]
    placeholder: bool = Field(default=False, description="True if this is a stub response (pipeline not yet wired)")
