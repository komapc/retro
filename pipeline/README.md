# TruthMachine Pipeline

Python pipeline for retroactive media prediction extraction and scoring.

## Structure

```
pipeline/
  src/tm/
    config.py           # settings via pydantic-settings
    models.py           # pydantic schemas (LLM output + matrix state)
    gatekeeper.py       # stage 1: is this a prediction? (Gemini Flash)
    extractor.py        # stage 2: forensic metric extraction (DeepSeek)
    runner.py           # orchestrates gatekeeper → extraction per article
    orchestrator.py     # batch runner: events × sources, local_file and api modes
    progress.py         # matrix state tracker + rich terminal visualizer
    backtest.py         # LightGBM backtest vs Polymarket (see BACKTEST.md)
  tests/
    test_models.py
  smoke_test.py         # 3 hardcoded articles, full pipeline run
  BACKTEST.md           # backtest design rationale and usage
```

## Setup

```bash
cd pipeline
cp .env.example .env   # add OPENROUTER_API_KEY
uv sync
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter key for gatekeeper + extractor LLM calls |
| `DATA_DIR` | No | Path to data directory (default: `../data`) |
| `VAULT_DIR` | No | Path to vault directory (default: `$DATA_DIR/vault`) |

> **Note:** `vault/` may be root-owned if previously created inside Docker. Set `VAULT_DIR` to a
> user-writable path (e.g. `data/vault2/`) to avoid permission errors when running locally.

## Running the orchestrator

The orchestrator processes articles from `data/raw_ingest/` through the full LLM pipeline and
writes scored entries to `data/atlas/`.

```bash
# local_file mode — reads from data/raw_ingest/{source}/{event}/article_*.json
DATA_DIR=/path/to/data VAULT_DIR=/path/to/data/vault2 \
  uv run python -m tm.orchestrator local_file

# api mode — fetches articles via Brave Search API
DATA_DIR=/path/to/data VAULT_DIR=/path/to/data/vault2 \
  uv run python -m tm.orchestrator api
```

### Raw ingest article format

Articles go in `data/raw_ingest/{source_id}/{event_id}/article_*.json`:

```json
{
  "headline": "Article headline",
  "text": "Full article text...",
  "published_at": "YYYY-MM-DD",
  "author": "Reporter Name",
  "url": "https://..."
}
```

The `published_at` date must fall within the prediction window (3–30 days before the event's
`outcome_date`) or the article will be filtered out by the backtest.

## Running the backtest

After the orchestrator has populated `data/atlas/`, run:

```bash
# Specific events
DATA_DIR=/path/to/data \
  uv run python -m tm.backtest --events A01 A02 A04 A05 --output data/backtest/

# All resolved events
DATA_DIR=/path/to/data \
  uv run python -m tm.backtest --all-resolved --output data/backtest/

# Force weighted average (skip LightGBM)
DATA_DIR=/path/to/data \
  uv run python -m tm.backtest --all-resolved --no-lgbm
```

LightGBM requires at least 5 events with atlas entries; below that it falls back to weighted
average. See `BACKTEST.md` for full design rationale and output interpretation.

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
| 1 | `gatekeeper.py` | Gemini 2.0 Flash | filter — is this article a prediction? |
| 2 | `extractor.py` | DeepSeek Chat | extract 11 forensic metrics per prediction |
| 3 | `runner.py` | — | orchestrate stages 1+2 per article |
| 4 | `orchestrator.py` | — | batch across all events × sources |
| 5 | `backtest.py` | LightGBM | compare predictions to Polymarket via Brier score |

## Known issues

- `data/vault/` created inside Docker is root-owned. Use `VAULT_DIR` env var to redirect writes
  to a user-writable path when running locally.
- `data/atlas/{event}/{source}/entry_*.json` files created inside Docker are root-owned and
  cannot be overwritten locally. New entries use a `_v2` suffix to avoid the conflict.
