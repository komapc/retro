# Oracle API — TruthMachine Forecast Service

> **Subdomain:** `oracle.daatan.com`
> **Status:** Phases 1–5 complete and live. Wired into daatan v1.9.0.

## Overview

The Oracle API is a FastAPI microservice that lives in `retro/api/`. Given a binary question, it:

1. Searches for relevant news articles (`web_search.py` — Serper.dev → Brave → DDG)
2. Runs each article through the TruthMachine pipeline (gatekeeper → extractor)
3. Weights each source's predictions by its historical Brier score from `leaderboard.json`
4. Aggregates into a calibrated probability distribution and returns it

It is called by **daatan** (the prediction market) to give bots and users an AI-sourced probability estimate for any question.

---

## Architecture Decision

**12 options were evaluated.** The chosen architecture:

- **FastAPI microservice inside the `retro` repo** — imports pipeline code directly, no porting
- **Separate systemd service** (`oracle-api.service`) on the retro EC2 alongside the batch pipeline
- **Retro EC2 is the intelligence backend** — daatan is the marketplace frontend
- **Git submodules were rejected** — `pip install -e ../pipeline` via `[tool.uv.sources]` is cleaner for Python
- **TypeScript port was rejected** — pipeline is ~2000 lines of Python with ML deps; porting is months of work

See `ARCHITECTURE.md` for the full comparison.

---

## Security

Two independent layers:

### Layer 1 — AWS Security Group
Port 8001 is not exposed to the public internet. Only the daatan EC2 security group ID is allowed as an inbound source. Survives IP changes.

### Layer 2 — Shared Bearer Secret
`x-api-key` header on every request. Both sides read from env. Same pattern as daatan's `BOT_RUNNER_SECRET`.

```
AWS SG: daatan-ec2-sg → retro-ec2:8001
App:    x-api-key: $ORACLE_API_KEY
```

---

## API Reference

### `POST /forecast`

**Auth:** `x-api-key` header required.
**Rate limit:** 10 requests/minute per IP.

```json
// Request
{
  "question": "Will the Israeli coalition government collapse in 2025?",
  "max_articles": 5
}

// Response
{
  "question": "Will the Israeli coalition government collapse in 2025?",
  "mean": 0.42,
  "std": 0.18,
  "ci_low": 0.14,
  "ci_high": 0.70,
  "articles_used": 4,
  "sources": [
    {
      "source_id": "haaretz",
      "source_name": "Haaretz",
      "url": "https://haaretz.com/...",
      "stance": 0.6,
      "certainty": 0.75,
      "credibility_weight": 1.04,
      "claims": ["Coalition crisis likely after Haredi draft bill fails"]
    }
  ]
}
```

**`mean` is in stance space `[-1, 1]`:**
- `+1` = all sources certain the event will happen
- `-1` = all sources certain it won't
- `0` = neutral / mixed
- Convert to probability: `p = (mean + 1) / 2`

### `GET /health`

No auth required. Returns:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "leaderboard_sources": 27
}
```

`version` allows clients to verify API compatibility before relying on `/forecast` responses.

---

## Deployment

### Directory structure

```
retro/
├── api/
│   ├── pyproject.toml          ← standalone package; depends on ../pipeline
│   ├── .env.example
│   └── src/forecast_api/
│       ├── main.py             ← FastAPI app + lifespan
│       ├── config.py           ← settings (extends tm.config pattern)
│       ├── auth.py             ← x-api-key dependency
│       ├── limiter.py          ← slowapi rate limiting
│       ├── leaderboard.py      ← load/cache/refresh leaderboard.json
│       ├── forecaster.py       ← core: search → extract → weight → aggregate
│       └── models.py           ← Pydantic request/response schemas
├── infra/
│   ├── oracle-api.service      ← systemd unit for the API process
│   └── ...
```

### First-time EC2 setup

```bash
cd ~/truthmachine
git pull origin main

# Install API deps (shares uv toolchain with pipeline)
cd api
uv sync

# Add to .env
echo "ORACLE_API_KEY=<generate-with: openssl rand -hex 32>" >> ../.env

# Install and start systemd unit
sudo cp ~/truthmachine/infra/oracle-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable oracle-api
sudo systemctl start oracle-api
```

### Smoke test

```bash
curl -s -X POST http://127.0.0.1:8001/forecast \
  -H "x-api-key: $ORACLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Will Netanyahu remain PM through 2025?"}'
```

### Updating (zero-downtime reload)

Since the service is supervised by gunicorn, routine deploys use `reload`, not
`restart`. The gunicorn master keeps the :8001 listening socket open while it
swaps workers with fresh code, so clients see no 502s.

```bash
cd ~/truthmachine
git pull origin main
cd api && uv sync --frozen

# Smoke-check imports BEFORE reloading — if this fails, abort.
# Old workers keep serving; we never reload broken code.
ORACLE_API_KEY=dummy uv run python -c "from forecast_api.main import app"

# Zero-downtime swap — master keeps the socket; workers recycle gracefully.
sudo systemctl reload oracle-api

# Verify /health returns the new version.
curl -s http://127.0.0.1:8001/health | jq .
```

Verify the reload window is truly seamless (run in another terminal before
reloading):

```bash
while true; do
  curl -s -o /dev/null -w "%{http_code} " http://127.0.0.1:8001/health
  sleep 0.1
done
# Expect a continuous stream of 200s across the reload.
```

### When to use `restart` instead of `reload`

- The systemd unit file itself changed (`ExecStart`, env vars, etc.) — run
  `sudo systemctl daemon-reload && sudo systemctl restart oracle-api`. This
  incurs a 2-5s 502 window.
- Gunicorn master itself crashed or needs new flags.
- Dependency-graph changes that require a fresh Python interpreter.

For routine app-code deploys (forecaster, models, config defaults), `reload`
is always sufficient and strictly preferred.

---

## Nginx routing (oracle.daatan.com)

Add to retro EC2 nginx (or to daatan's nginx if co-hosted):

```nginx
upstream oracle_api {
    server 127.0.0.1:8001;
    keepalive 4;
}

server {
    listen 443 ssl http2;
    server_name oracle.daatan.com;

    ssl_certificate /etc/letsencrypt/live/oracle.daatan.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/oracle.daatan.com/privkey.pem;

    location / {
        proxy_pass http://oracle_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 20s;
        limit_req zone=llm_limit burst=5 nodelay;
        limit_req_status 429;
    }
}
```

---

## daatan integration (live since v1.9.0)

The Oracle is wired into two `daatan` routes, with automatic fallback to the existing LLM `guessChances` path when the Oracle is unavailable, returns a placeholder, or times out:

| Route | File |
|-------|------|
| `POST /api/forecasts/[id]/context` | `daatan/src/app/api/forecasts/[id]/context/route.ts` |
| `POST /api/forecasts/express/guess` | `daatan/src/app/api/forecasts/express/guess/route.ts` |

Client: `daatan/src/lib/services/oracle.ts` — `getOracleProbability()` returns a probability in `[0, 1]` or `null` (never throws). `checkOracleHealth()` verifies the API is reachable and its version starts with `0.1`.

### Secret management

The shared `x-api-key` lives in AWS Secrets Manager at `openclaw/oracle-api-key` (region `eu-central-1`). The `openclaw/` prefix is legacy naming from the decommissioned OpenClaw stack and is retained for backwards compatibility with `ec2_bootstrap.sh`. Both sides read the key from there:

- **retro EC2** (`oracle-api.service`) — `ORACLE_API_KEY` env var
- **daatan EC2** (`~/app/.env`) — `ORACLE_URL` + `ORACLE_API_KEY`, pulled via `scripts/fetch-secrets.sh` from the `daatan-env-prod` / `daatan-env-staging` bundle secret on each deploy

To rotate: update `openclaw/oracle-api-key` in Secrets Manager, then update both `daatan-env-{prod,staging}` bundles and the EC2 `.env` on the retro side, and restart both services.

---

## Roadmap

| Phase | Description |
|---|---|
| ✅ Phase 1 | API skeleton + auth + rate limiting |
| ✅ Phase 2 | Live pipeline: `web_search.py` → gatekeeper → extractor → leaderboard weighting |
| ✅ Phase 3 | Leaderboard credibility weighting (TrueSkill conservative score) |
| ✅ Phase 4 | `oracle.daatan.com` DNS + TLS + EC2 deploy |
| ✅ Phase 5 | daatan integration — `oracle.ts` client wired into context + express guess routes (shipped in daatan v1.9.0) |
| 🔲 Phase 6 | Async queue for >15s requests |
