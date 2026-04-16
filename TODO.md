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
- [ ] **Deploy `oracle-api.service`** to retro EC2 (`sudo systemctl enable oracle-api`)
- [ ] **DNS** — point `oracle.daatan.com` → retro EC2, issue TLS cert via certbot
- [ ] **nginx vhost** — deploy `infra/nginx/oracle.conf` on retro EC2
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

## Scoring

- [ ] Time-decay Brier score — predictions made closer to the event date should count more
  (or less, depending on design goal). Currently all predictions are weighted equally.

- [ ] Calibration curve — plot implied_p vs actual outcome rate across probability buckets.
