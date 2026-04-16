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
- [ ] **daatan secrets** — add `ORACLE_URL` + `ORACLE_API_KEY` to daatan `.env` / AWS Secrets Manager
- [ ] **daatan bot integration** — wire `oracle.ts` into the bot-runner for probability estimates

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

## Bugs (from code review 2026-04-16)

- [ ] **`*.json` glob catches `cell_signal.json`** — `render_atlas.py`, `scorer.py`, and `generate_pages.py`
  use `glob("*.json")` per source dir, which includes `cell_signal.json` alongside `entry_*.json`.
  This can distort Brier scores and prediction counts. Filter to `entry_*.json` only.

- [ ] **Silent failure masking** — `orchestrator.py` overwrites `failed` status with `no_predictions`
  when no predictions are found, hiding real LLM errors. Check `has_predictions` only if no runner
  errors occurred.

- [ ] **`backtest.py` uses `event.get("title")`** — should be `event.get("name")`. Polymarket lookup
  likely fails silently for most events.

- [ ] **`check_keys.sh` has a hardcoded Serper API key** — committed secret in `infra/check_keys.sh`.
  Remove and read from Secrets Manager or env instead.

- [ ] **`placeholder` field never set to `True`** — `forecaster.py` `_empty_response` returns
  `placeholder=False` even when no articles are found. Should distinguish "no data" from "real forecast".
