# TruthMachine Pipeline

Python pipeline for retroactive media prediction extraction and scoring.

## Structure

```
pipeline/
  src/tm/
    config.py       # settings via pydantic-settings
    models.py       # pydantic schemas (LLM output + matrix state)
    gatekeeper.py   # stage 1: is this a prediction? (cheap model)
    extractor.py    # stage 2: forensic metric extraction (DeepSeek)
    progress.py     # matrix state tracker + rich terminal visualizer
    runner.py       # orchestrates gatekeeper → extraction per article
  tests/
    test_models.py
  smoke_test.py     # 3 hardcoded articles, full pipeline run
```

## Setup

```bash
cd pipeline
cp .env.example .env   # add OPENROUTER_API_KEY
uv sync
```

## Run smoke test

```bash
uv run python smoke_test.py
```

Runs 3 articles (1 English, 1 Hebrew, 1 non-prediction) through the full pipeline and renders the matrix progress grid.

## Matrix visualization

The progress grid shows all events × sources as a compact terminal table:

```
         YNT HAA N12 ...
  A01     ▓   ▓   ░
  A02     ░   ▒   ░
  B01     ✗   ▓   ·

░ pending  ▒ in_progress  ▓ done  ✗ failed  · no predictions
Progress: 3/250 (1.2%) | done: 2 | no_pred: 1 | failed: 0
```

## Pipeline stages

| Stage | File | Model | Purpose |
|---|---|---|---|
| 1 | `gatekeeper.py` | cheap (Hermes/Nano) | filter — is this a prediction? |
| 2 | `extractor.py` | DeepSeek V3.2 | extract all metrics |
| 3 | `progress.py` | — | update matrix state |
