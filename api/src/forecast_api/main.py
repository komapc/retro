import asyncio
import logging
import re
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi.errors import RateLimitExceeded

from .auth import verify_api_key
from .cache import forecast_cache
from .config import settings
from .forecaster import run_forecast
from .leaderboard import background_refresh_loop, leaderboard_size, refresh_cache
from .limiter import limiter
from .models import ForecastRequest, ForecastResponse, SearchRequest, SearchResponse, SearchHealthResponse
from .searcher import run_search, run_search_health

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    path = settings.resolved_leaderboard_path
    await refresh_cache(path)
    logger.info("Oracle API starting — leaderboard: %d sources, port: %d", leaderboard_size(), settings.port)
    refresh_task = asyncio.create_task(
        background_refresh_loop(path, settings.leaderboard_refresh_seconds)
    )
    yield
    # Shutdown
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        pass
    logger.info("Oracle API shut down")


_CORS_ORIGIN = "https://komapc.github.io"
_CORS_ORIGINS = {_CORS_ORIGIN, "https://bayes.daatan.com"}


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in _CORS_ORIGINS or origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Headers"] = "Content-Type, x-api-key"
        headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return JSONResponse({"detail": "Rate limit exceeded — max 10 requests/minute"}, status_code=429, headers=headers)


app = FastAPI(
    title="TruthMachine Oracle API",
    description="Calibrated probability estimates for binary questions, weighted by historical source accuracy.",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

# Allow oracle-test.html on GitHub Pages to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://komapc.github.io",
        "https://bayes.daatan.com",
        "http://localhost:*",
        "http://127.0.0.1:*",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "x-api-key"],
)


@app.get("/", include_in_schema=False)
async def root():
    """Redirect to the interactive test console."""
    return RedirectResponse("https://komapc.github.io/retro/oracle-test.html")


@app.get("/health", tags=["Meta"])
async def health():
    """Liveness probe — no auth required."""
    return {
        "status": "ok",
        "version": app.version,
        "leaderboard_sources": leaderboard_size(),
        "cache": {
            "enabled": forecast_cache.enabled,
            **forecast_cache.stats().as_dict(),
        },
    }


@app.post("/forecast", response_model=ForecastResponse, tags=["Forecast"])
@limiter.limit("10/minute")
async def forecast(
    request: Request,  # required by slowapi
    body: ForecastRequest,
    _: None = Depends(verify_api_key),
):
    """
    Given a binary question, return a calibrated probability distribution.

    The `mean` field is in stance space [-1, 1].
    Convert to probability [0, 1] with: `p = (mean + 1) / 2`
    """
    return await run_forecast(body)


@app.post("/search", response_model=SearchResponse, tags=["Search"])
@limiter.limit("60/minute")
async def search(
    request: Request,  # required by slowapi
    body: SearchRequest,
    _: None = Depends(verify_api_key),
):
    """
    Search for news articles using the full provider fallback chain.

    Tries: SerpAPI → Serper → Brave → BrightData → Nimbleway → ScrapingBee → DDG.
    DDG is skipped when the service is running on EC2.
    """
    return await run_search(body)


@app.get("/search/health", response_model=SearchHealthResponse, tags=["Search"])
async def search_health(_: None = Depends(verify_api_key)):
    """
    Per-provider search health: key configured, in-process quota flag, and live credit
    count where the provider exposes a credit API (Serper, SerpAPI, ScrapingBee).
    """
    return await run_search_health()


_GAMMA_BASE = "https://gamma-api.polymarket.com"
_GAMMA_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TruthMachine/1.0)"}
_ID_RE = re.compile(r"^\d+(,\d+)*$")


@app.get("/pm/markets", tags=["Polymarket"])
@limiter.limit("30/minute")
async def pm_markets(
    request: Request,
    id: str = Query(..., description="Comma-separated Gamma market IDs"),
):
    """
    Proxy for Polymarket Gamma API — returns live market data with CORS headers.
    Gamma API does not send Access-Control-Allow-Origin, so browser fetches from
    GitHub Pages are blocked; this endpoint forwards the request server-side.
    """
    if not _ID_RE.match(id):
        return JSONResponse({"detail": "id must be comma-separated integers"}, status_code=422)
    ids = id.split(",")
    if len(ids) > 50:
        return JSONResponse({"detail": "max 50 ids per request"}, status_code=422)

    # Build URL directly — httpx would percent-encode commas in params=,
    # but gamma-api requires literal commas: ?id=111,222,333
    url = f"{_GAMMA_BASE}/markets?id={id}&limit={len(ids)}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=_GAMMA_HEADERS)
        resp.raise_for_status()
    return JSONResponse(resp.json())
