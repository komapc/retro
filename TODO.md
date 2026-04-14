# TruthMachine TODO

## Oracle API (oracle.daatan.com)

- [x] API skeleton — FastAPI app with placeholder forecaster (`api/`)
- [x] Test console deployed to GitHub Pages
- [ ] **Phase 2: Wire up pipeline** — replace stub in `forecaster.py` with:
  1. `web_search.search_articles(question, limit)` via `asyncio.to_thread`
  2. `gatekeeper.check_is_prediction()` + `extractor.extract_predictions()` in parallel per article
  3. `leaderboard.get_credibility_weight(source_id)` weighting
  4. Weighted mean + 95% CI aggregation
- [ ] Deploy `oracle-api.service` to retro EC2 (`sudo systemctl enable oracle-api`)
- [ ] Point `oracle.daatan.com` DNS → retro EC2, issue TLS cert
- [ ] Add nginx vhost for `oracle.daatan.com` (see `docs/ORACLE_API.md`)
- [ ] Add `ORACLE_URL` + `ORACLE_API_KEY` secrets to daatan `.env` / AWS Secrets Manager
- [ ] Wire daatan bot-runner to call `oracle.ts` for probability estimates

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
