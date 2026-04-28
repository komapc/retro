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
- [ ] Unify env var names: `SERPAPI_KEY` → `SERPAPI_API_KEY`, `SERPERDEV_KEY` → `SERPER_API_KEY` in `web_search.py` (do atomically: update SM paths, update code, reload)

### Phase 3 — Observability (after Phase 2 stable)

- [ ] Add `search_provider_used=<name>` field to oracle's structured `_log_phase("search", ...)` output
- [ ] Add hourly cron route in daatan (`/api/cron/search-health`) polling oracle's `/search/health`; fire Telegram on low credits
- [ ] Add `notifyOracleSearchUnavailable()` to daatan `telegram.ts` (fired when oracleSearch times out/errors, rate-limited to 5 min)
- [ ] Add key-refresh logic to pipeline: re-fetch from Secrets Manager if cached key is >24h old (currently refreshed only on process restart)

## Ingest / Coverage

- [ ] **GDELT DOC API** — query `doc.gdeltproject.org/api/v2/artlist` by domain + keyword + date range.
  Free, no API key, strong coverage for English sources. Good complement to Wayback CDX for
  events where CDX coverage is sparse. Implement as a second fallback after CDX, or run in
  parallel with GNews. Hebrew coverage is weaker.

## Data Quality

- [ ] Audit `llm_referee_criteria` for all 70 events — many are placeholders (e.g. `"B, E"`).
  Replace with a clear binary question ("Will X happen?") so the extractor can anchor stance
  correctly. Then `--force-reextract` affected events.

## Duel: TruthMachine vs Polymarket

- [x] Polymarket harvest pipeline (`polymarket_harvest.py`) — bulk harvest of resolved political markets
- [x] PoC event generation (`poc_event_gen.py`) — convert harvested markets → pipeline event JSONs
- [x] Duel report generator (`poc_report.py`) — interactive HTML with charts, calibration, event browser
- [x] `duel.html` generated and deployed to GitHub Pages
- [ ] **Wire TM predictions into duel report** — the "TruthMachine vs Polymarket" section is still a placeholder
- [ ] **Brier comparison** — compute TM Brier vs PM Brier per event and display in the duel page

## Scoring

- [ ] Time-decay Brier score — predictions made closer to the event date should count more
  (or less, depending on design goal). Currently all predictions are weighted equally.

- [ ] Calibration curve — plot implied_p vs actual outcome rate across probability buckets.

## Bugs (from code review 2026-04-16) — all resolved in PR #35

- [x] **`*.json` glob catches `cell_signal.json`** — filter to `entry_*.json` in `render_atlas.py`, `scorer.py`, `generate_pages.py`
- [x] **Silent failure masking** — `orchestrator.py` no longer overwrites `failed` with `no_predictions`
- [x] **`backtest.py` uses `event.get("title")`** — fixed to `event.get("name")`
- [x] **`check_keys.sh` has a hardcoded Serper API key** — moved to AWS Secrets Manager (`openclaw/serperdev-key`)
- [x] **`placeholder` field never set to `True`** — `_empty_response` now returns `placeholder=True`
