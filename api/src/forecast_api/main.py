import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi.errors import RateLimitExceeded

from .auth import verify_api_key
from .config import settings
from .forecaster import run_forecast
from .leaderboard import background_refresh_loop, leaderboard_size, refresh_cache
from .limiter import limiter
from .models import ForecastRequest, ForecastResponse

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


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse({"detail": "Rate limit exceeded — max 10 requests/minute"}, status_code=429)


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
    return {"status": "ok", "leaderboard_sources": leaderboard_size()}


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
