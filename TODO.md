# TruthMachine TODO

## Oracle API (oracle.daatan.com)

- [x] API skeleton — FastAPI app with auth + rate limiting (`api/`)
- [x] Test console deployed to GitHub Pages
- [x] **Phase 2: Pipeline wired** — `forecaster.py` fully implemented:
  - `web_search.search_articles()` (SerpAPI → Serper → Brave → DDG) via `asyncio.to_thread`
  - trafilatura full-text fetch per article
  - `gatekeeper` + `extractor` in parallel per article
  - `leaderboard.get_credibility_weight()` — TrueSkill conservative score
  - Weighted mean + 95% CI aggregation
- [x] Leaderboard credibility weighting live (`api/src/forecast_api/leaderboard.py`)
- [x] **Deploy `oracle-api.service`** — running on retro EC2, enabled + auto-restart
- [x] **DNS + TLS** — `oracle.daatan.com` live, Let's Encrypt cert issued
- [x] **nginx vhost** — `infra/nginx/oracle.conf` deployed, HTTP→HTTPS redirect active
- [x] **`/health` endpoint returns version** — daatan client can detect API incompatibility
- [x] **daatan secrets** — `ORACLE_URL` + `ORACLE_API_KEY` added to `daatan-env-{prod,staging}` in AWS Secrets Manager; standalone `openclaw/oracle-api-key` for rotation
- [x] **daatan integration** — `oracle.ts` wired into `context` + `express/guess` routes with LLM fallback (shipped in daatan v1.9.0)
- [ ] **daatan bot integration** — wire `getOracleProbability` into the bot-runner so autonomous bots use the Oracle when forming their predictions

## Search & Secrets Unification

> Context: all three paid providers (SerpAPI, Serper, Brave) exhausted simultaneously on 2026-04-28,
> causing the oracle to return `placeholder:true` for all requests. Root cause: oracle and daatan were
> consuming the same provider quotas independently with no visibility into each other's usage.
> Full plan: see conversation 2026-04-28 ("Create an elaborate plan FOR BOTH REPOS").

### Phase 1 — Expand provider chain ✅ Done (2026-04-28)

- [x] Add BrightData, Nimbleway, ScrapingBee to `web_search.py` (fallback chain is now 6 providers + DDG)
- [x] Keys stored in Secrets Manager (`openclaw/brightdata-api-key`, `openclaw/nimbleway-api-key`, `openclaw/scrapingbee-api-key`)
- [x] IAM policy `openclaw-secrets-read` applied to `truthmachine-ec2-role` (GetSecretValue on `openclaw/*`)
- [x] Deployed to both EC2 worktrees (`oracle-api` + `truthmachine`); services reloaded
- [x] `BRIGHTDATA_API_KEY` + `NIMBLEWAY_API_KEY` added to daatan `src/env.ts` Zod schema

### Phase 2 — Oracle as search gateway ✅ Done (2026-04-28)

- [x] `POST /search` — `searcher.run_search()` via `asyncio.to_thread`; 60/min rate limit; query, limit, date_from, date_to
- [x] `GET /search/health` — per-provider: configured, in-process exhaustion flag, live credits where API exists (Serper → balance, SerpAPI → searches_left, ScrapingBee → max-used). Overall: ok/degraded/down
- [ ] Create `src/lib/services/oracleSearch.ts` in daatan — thin client, returns `null` on failure *(tracked in daatan TODO)*
- [ ] Update `context/route.ts` + `research/route.ts` in daatan: try `oracleSearch` first, fall through to local `searchArticles` on failure *(tracked in daatan TODO)*
- [x] Unify env var names: `SERPAPI_KEY` → `SERPAPI_API_KEY`, `SERPERDEV_KEY` → `SERPER_API_KEY` in `web_search.py`

### Phase 3 — Observability ✅ Done (2026-04-28, retro side)

- [x] `search_provider_used=<name>` in `_log_phase("search", ...)` — thread-local set inside `search_articles()`, read in `forecaster.py` after the thread returns
- [x] Key-refresh logic — `_refresh_keys_if_stale()` called at top of `search_articles()`; re-fetches all keys from Secrets Manager after 24h
- [ ] Hourly cron route in daatan (`/api/cron/search-health`) polling oracle's `/search/health`; fire Telegram on low credits *(daatan side, pending)*
- [x] `notifyOracleSearchUnavailable()` — done in daatan PR #699

## Ingest / Coverage

- [x] **GDELT DOC API** — already implemented as Step 4 fallback in `gnews_ingest.py` (`search_gdelt()`, circuit-breaker, rate-limiting). No further work needed.

## Data Quality

- [x] Audit `llm_referee_criteria` for all 70 events — all 70 have proper binary criteria. No placeholders found.

## Duel: TruthMachine vs Polymarket

- [x] Polymarket harvest pipeline (`polymarket_harvest.py`) — bulk harvest of resolved political markets
- [x] PoC event generation (`poc_event_gen.py`) — convert harvested markets → pipeline event JSONs
- [x] Duel report generator (`poc_report.py`) — interactive HTML with charts, calibration, event browser
- [x] `duel.html` generated and deployed to GitHub Pages
- [x] **Wire TM predictions into duel report** — `load_tm_predictions()` scans vault2/extractions, mean stance → probability per event
- [x] **Brier comparison** — TM Brier vs PM Brier per event; avg comparison bar chart + scatter plot; per-event table with winner column

## Scoring

- [x] Time-decay Brier score — `time_decay_weight(article_date, outcome_date, half_life_days=30)` in `scorer.py`; exponential decay so predictions closer to the event weigh more; `time_decay_brier_score` added to leaderboard entries.

- [x] Calibration curve — `_compute_calibration_bins()` in both `scorer.py` (writes `data/calibration.json`) and `render_atlas.py` (inline Chart.js scatter in the Scoring section); `poc_report.py` already has PM calibration.

## Bugs (from code review 2026-04-16) — all resolved in PR #35

- [x] **`*.json` glob catches `cell_signal.json`** — filter to `entry_*.json` in `render_atlas.py`, `scorer.py`, `generate_pages.py`
- [x] **Silent failure masking** — `orchestrator.py` no longer overwrites `failed` with `no_predictions`
- [x] **`backtest.py` uses `event.get("title")`** — fixed to `event.get("name")`
- [x] **`check_keys.sh` has a hardcoded Serper API key** — moved to AWS Secrets Manager (`openclaw/serperdev-key`)
- [x] **`placeholder` field never set to `True`** — `_empty_response` now returns `placeholder=True`
