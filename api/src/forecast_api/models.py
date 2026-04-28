from typing import Optional
from pydantic import BaseModel, Field


# ── Search ────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Search query string")
    limit: int = Field(default=5, ge=1, le=20, description="Max results to return")
    date_from: Optional[str] = Field(default=None, description="ISO date lower bound YYYY-MM-DD")
    date_to: Optional[str] = Field(default=None, description="ISO date upper bound YYYY-MM-DD")


class SearchResultItem(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = ""
    published_date: str = ""


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    count: int


class ProviderStatus(BaseModel):
    configured: bool
    exhausted: bool = Field(description="In-process quota-exhausted flag (resets on restart)")
    status: str = Field(description="'ok' | 'exhausted' | 'not_configured' | 'error'")
    credits: Optional[int] = Field(default=None, description="Remaining credits from provider API, if available")
    error: Optional[str] = Field(default=None)


class SearchHealthResponse(BaseModel):
    providers: dict[str, ProviderStatus]
    overall: str = Field(description="'ok' (≥2 usable) | 'degraded' (1 usable) | 'down' (0 usable on EC2)")
    usable_count: int = Field(description="Number of configured, non-exhausted providers (excluding DDG)")


# ── Forecast ──────────────────────────────────────────────────────────────────

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
