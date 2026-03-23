# TruthMachine TODO

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
