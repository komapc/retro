# TruthMachine — System Architecture

## Overview

TruthMachine (Factum Atlas) is a retroactive media analysis pipeline that:
1. Collects news articles published **before** known past events
2. Extracts and quantifies forward-looking predictions from each article
3. Scores each prediction against the actual outcome (Brier score)
4. Renders an interactive coverage matrix at **komapc.github.io/retro**

---

## Repository Structure

```
retro/
├── api/                         # Oracle API — FastAPI microservice (oracle.daatan.com)
│   ├── src/forecast_api/
│   │   ├── main.py              # FastAPI app + lifespan
│   │   ├── forecaster.py        # Core: search → extract → weight → aggregate
│   │   ├── leaderboard.py       # Load/cache leaderboard.json for credibility weights
│   │   ├── models.py            # Pydantic request/response schemas
│   │   ├── config.py            # Settings (extends tm.config pattern)
│   │   ├── auth.py              # x-api-key dependency
│   │   └── limiter.py           # slowapi rate limiting
│   └── pyproject.toml
├── pipeline/                    # Python pipeline (uv project)
│   ├── src/tm/
│   │   ├── config.py            # Settings (models, API keys via .env)
│   │   ├── models.py            # Pydantic models (Prediction, ExtractionOutput, CellSignal, etc.)
│   │   ├── progress.py          # progress.json read/write helpers + rich terminal visualizer
│   │   │
│   │   ├── # --- Ingest ---
│   │   ├── gnews_ingest.py      # GNews RSS → URL resolution → trafilatura + Wayback fallback
│   │   ├── gdelt_ingest.py      # GDELT Doc 2.0 API batch ingestor (sequential, rate-limited)
│   │   ├── ingestor.py          # Pluggable ingestor classes: DDGIngestor, GDELTIngestor
│   │   ├── site_search.py       # Direct site-search scraper (no API key, high reliability)
│   │   ├── web_search.py        # Multi-provider news search: SerpAPI → Serper → Brave → DDG
│   │   ├── polymarket.py        # Polymarket Gamma API: fetch market history per event
│   │   ├── polymarket_harvest.py # Bulk harvest of all resolved Polymarket political markets
│   │   │
│   │   ├── # --- Extraction ---
│   │   ├── gatekeeper.py        # LLM stage 1: does this article contain predictions?
│   │   ├── extractor.py         # LLM stage 2: extract structured predictions from article
│   │   ├── runner.py            # Orchestrates gatekeeper → extractor per article
│   │   ├── aggregator.py        # Cell-level: collapse all predictions for (event, source) → CellSignal
│   │   ├── reaggregate.py       # Post-processing: re-run aggregation on high-variance cells
│   │   │
│   │   ├── # --- Scoring & Output ---
│   │   ├── orchestrator.py      # Batch runner: events × sources → vault → atlas
│   │   ├── scorer.py            # Brier score + calibration utilities + per-category scoring
│   │   ├── backtest.py          # LightGBM backtest + Polymarket comparison
│   │   ├── render_atlas.py      # Renders factum_atlas.html from atlas/ data
│   │   ├── generate_pages.py    # Generates per-event/source static HTML pages
│   │   ├── sync_atlas.py        # Parses event table and syncs atlas entry JSON files
│   │   │
│   │   ├── # --- One-off scripts ---
│   │   ├── init_db.py           # Initialize SQLite DB for progress tracking
│   │   ├── migrate_cell_signals.py # One-time: compute cell_signal.json from existing vault data
│   │   ├── poc_event_gen.py     # Convert harvested Polymarket events → pipeline event JSONs
│   │   ├── poc_report.py        # Generate duel.html — TruthMachine vs Polymarket comparison report
│   │   ├── create_real_samples.py  # Create real sample data for testing
│   │   └── create_sample_data.py   # Create synthetic sample data for testing
│   ├── scripts/
│   │   └── improve_keywords.py  # One-time: LLM-generate search keywords for events
│   ├── tests/                   # pytest test suite
│   ├── smoke_test.py            # 3 hardcoded articles through full pipeline
│   ├── test_run.py              # Manual test runner
│   ├── docker-compose.yml       # Local pipeline stack
│   ├── pyproject.toml
│   └── Dockerfile
├── data/                        # Gitignored except events/ and sources/
│   ├── events/                  # Event definitions (TRACKED IN GIT)
│   ├── sources/                 # Source definitions (TRACKED IN GIT)
│   ├── raw_ingest/              # Scraped articles (regeneratable, not in git)
│   ├── vault2/
│   │   ├── articles/            # Deduplicated article cache by SHA-256 hash
│   │   └── extractions/         # LLM extraction cache: {hash}_{event_id}_v1.json
│   ├── atlas/                   # Atlas link files: atlas/{event_id}/{source_id}/entry_*.json
│   └── progress.json            # Cell status: done/pending/no_predictions/failed
├── infra/
│   ├── ec2_bootstrap.sh         # One-time EC2 setup script
│   ├── ec2_run.sh               # Hourly pipeline loop (runs on EC2)
│   ├── ec2_run_poc.sh           # PoC pipeline run script
│   ├── monitor.sh               # Local monitoring script (polls EC2 via SSM)
│   ├── logs.sh                  # Tail EC2 pipeline logs via SSM
│   ├── check_keys.sh            # Verify required AWS Secrets Manager keys exist
│   ├── remote_stats.sh          # Fetch pipeline progress stats from EC2
│   ├── oracle-api.service       # systemd unit for the Oracle API process
│   ├── truthmachine.service     # systemd unit for the pipeline batch process
│   ├── truthmachine-poc.service # systemd unit for PoC pipeline variant
│   └── nginx/                   # Nginx config fragments (oracle.daatan.com vhost)
├── case-studies/                # Interactive case study pages
├── .github/workflows/
│   └── deploy-atlas.yml         # GitHub Actions: deploy factum_atlas.html + oracle-test + duel to Pages
├── factum_atlas.html            # Generated atlas (committed by EC2 after each cycle)
├── oracle-test.html             # Oracle API test console (deployed to GitHub Pages)
└── duel.html                    # TruthMachine vs Polymarket comparison report (generated by poc_report.py)
```

---

## Data Model

### Event (`data/events/{id}.json`)
```json
{
  "id": "C09",
  "name": "Assad regime falls in Syria",
  "outcome": true,
  "outcome_date": "2024-12-08",
  "predictive_window_days": 14,
  "search_keywords": ["נפילת אסד סוריה", "מרד סוריה דמשק", "Assad regime collapse Syria", ...],
  "llm_referee_criteria": "The Assad government loses effective control of Damascus.",
  "category": ["Regional Geopolitics"],
  "tags": ["Assad", "Syria", "regime collapse", "rebels"]
}
```

**`category`** — multi-label list from the taxonomy:
`Israeli Politics`, `Gaza War`, `Regional Geopolitics`, `Israeli Economy`, `Israeli Society`, `AI & Tech`, `Global`.
Used to compute per-category source accuracy scores for the forecasting model.

**`tags`** — free-form keywords for fine-grained topic matching at inference time.

### Source (`data/sources/{id}.json`)
```json
{
  "id": "toi",
  "name": "Times of Israel",
  "url": "https://www.timesofisrael.com",
  "language": "en"
}
```

### Atlas Entry (`data/atlas/{event_id}/{source_id}/entry_{hash[:8]}.json`)
```json
{
  "article_hash": "...",
  "extraction_id": "...",
  "headline": "...",
  "article_url": "https://...",
  "author": "...",
  "article_date": "2024-04-13",
  "event_date": "2024-04-14",
  "extractor_model": "bedrock/amazon.nova-lite-v1:0",
  "gatekeeper_model": "bedrock/amazon.nova-micro-v1:0",
  "gatekeeper_reason": "Article directly predicts an imminent Iranian missile strike on Israel.",
  "predictions": [...]
}
```

### Vault Extraction (`data/vault2/extractions/{hash}_{event}_v1.json`)
```json
{
  "extraction": { "predictions": [...] },
  "prompt_version": "v1",
  "extractor_model": "bedrock/amazon.nova-lite-v1:0",
  "gatekeeper_model": "bedrock/amazon.nova-micro-v1:0",
  "gatekeeper_reason": "...",
  "run_date": "2026-04-14T12:00:00"
}
```

### Prediction (extracted by LLM)
Each prediction has: `quote`, `claim`, `stance` (−1 to +1, event probability), `certainty`, `sentiment`, `specificity`, `hedge_ratio`, `conditionality`, `magnitude`, `time_horizon`, `prediction_type`, `source_authority`.

**stance** = how strongly the prediction implies the related event WILL occur.
- `+1.0` = author is certain the event will happen
- `−1.0` = author is certain the event will NOT happen
- `0.0`  = neutral / genuinely uncertain

---

## Pipeline Flow

```
Ingest (choose one):
  gnews_ingest.py  — GNews RSS → URL resolution (Brave/SerpAPI/Serper/DDG) → trafilatura
                     If 0 articles: CDX/Wayback fallback
  gdelt_ingest.py  — GDELT Doc 2.0 API, sequential with rate-limiting
  ingestor.py      — Pluggable DDGIngestor / GDELTIngestor classes
  site_search.py   — Direct site search scraper (no API key)
  All save to: data/raw_ingest/{source}/{event}/article_NN.json
  ▼
orchestrator.py  (local_file mode)
  │  For each (event, source) cell not yet done:
  │    runner.py → gatekeeper.py (LLM: has predictions?)
  │                extractor.py  (LLM: extract structured predictions)
  │    aggregator.py → cell_signal.json (collapse predictions → CellSignal)
  │    Save extraction to vault2/extractions/{hash}_{event}_v1.json
  │    Save atlas link to atlas/{event}/{source}/entry_{hash[:8]}.json
  │    Update progress.json → status: done
  ▼
render_atlas.py
  │  Load all atlas/ entries + cell signals
  │  Compute competitive Brier scores (scorer.py)
  │  Render factum_atlas.html (interactive matrix)
  ▼
git push → GitHub Actions → GitHub Pages
```

---

## LLM Models

| Role | Model | Notes |
|---|---|---|
| Gatekeeper | `bedrock/amazon.nova-micro-v1:0` | Fast yes/no: does article contain predictions? |
| Extractor | `bedrock/amazon.nova-lite-v1:0` | Structured extraction of up to 10 predictions |
| Article Aggregator | `bedrock/amazon.nova-lite-v1:0` | Collapses high-spread predictions within a single article |
| Keywords | `google/gemini-2.0-flash-001` | One-time: generate search keywords per event (via OpenRouter) |

All defaults via AWS Bedrock. Override via env vars in `pipeline/src/tm/config.py`. The `model_api_base` and `model_api_key` settings allow routing through any LiteLLM-compatible provider (OpenRouter, etc.).

---

## Scoring

**Competitive Brier Score** — only predictions from time windows where ≥2 sources published are scored. Single-source windows are excluded.

```
p = (stance + 1.0) / 2.0      # normalize stance to [0, 1]
brier = (p - outcome)²         # outcome = 1.0 if event happened, 0.0 if not
```

Configured in `render_atlas.py`:
```python
SCORING_CONFIG = ScoringConfig(window_hours=48, min_per_window=2)
```

**Confidence-weighted Brier Score** (`scorer.py`) — predictions with higher `certainty` carry more weight:

```
weight          = 0.5 + 1.5 × certainty      # range [0.5, 2.0]
weighted_brier  = brier × weight
```

**Per-category scoring** — `scorer.py` computes `brier_score` and `weighted_brier_score` both globally and broken down by `category` (e.g. "Gaza War", "AI & Tech"). Stored in `leaderboard.json` under `by_category`. Used by the forecasting model to select trusted sources per topic.

**ELO** — zero-sum rating updated after each event: sources that predicted correctly gain points from those that predicted incorrectly. Global only (per-category ELO planned).

---

## Ingest Sources (27 defined)

### Israeli — Hebrew
| Source | Domain |
|---|---|
| Haaretz | haaretz.co.il |
| Ynet | ynet.co.il |
| Israel Hayom | israelhayom.co.il |
| Walla News | news.walla.co.il |
| N12 (Mako) | n12.co.il |
| Maariv | maariv.co.il |
| Channel 13 | 13tv.co.il |
| Channel 14 (Now 14) | now14.co.il |
| Kan 11 | kan.org.il |
| Globes | globes.co.il |
| Calcalist | calcalist.co.il |
| The Marker | themarker.com |
| Uri Kurlianchik | kurlianchik.substack.com |

### Israeli — English
| Source | Domain |
|---|---|
| Times of Israel | timesofisrael.com |
| Jerusalem Post | jpost.com |

### International
| Source | Domain |
|---|---|
| Reuters | reuters.com |
| BBC News | bbc.com |
| CNN | cnn.com |
| Al Jazeera | aljazeera.com |
| Bloomberg | bloomberg.com |
| Wall Street Journal | wsj.com |
| The Guardian | theguardian.com |
| Axios | axios.com |
| Financial Times | ft.com |
| The New York Times | nytimes.com |
| The Washington Post | washingtonpost.com |

### Reference
| Source | Domain | Notes |
|---|---|---|
| Polymarket | polymarket.com | Ground truth pricing, not scored as a media source |

---

## Deployment

### Infrastructure
- **EC2**: `t4g.small`, Ubuntu, `eu-central-1` (Frankfurt)
- **Access**: AWS SSM Session Manager (no SSH key — instance has no key pair)
- **Instance name**: `truthmachine-pipeline` (`i-00ac444b94c5ff9b2`)
- **Public IP**: `3.120.185.111` (dynamic — reassigned on stop/start)
- **Terraform**: not in this repo. The EC2 instance was originally provisioned by
  the `openclaw` Terraform stack, which has since been decommissioned. The instance
  continues to run manually; a fresh Terraform module for TruthMachine would need
  to be authored if a replacement is ever required.

### Required Secrets (AWS Secrets Manager, `eu-central-1`)

> **Note on naming:** The secret names below are prefixed `openclaw/` for historical
> reasons — they predate the decommissioning of the OpenClaw stack. The secrets
> themselves are still in active use by TruthMachine/Oracle and should **not** be
> renamed without a coordinated update to `infra/ec2_bootstrap.sh`, `infra/check_keys.sh`,
> and the Oracle API service config.

| Secret name | Used by |
|---|---|
| `openclaw/openrouter-api-key` | LLM inference via OpenRouter (fallback) |
| `openclaw/brave-api-key` | URL resolution — Brave Search (optional) |
| `openclaw/serpapi-key` | URL resolution — SerpApi/Google (optional) |
| `openclaw/serperdev-key` | URL resolution — Serper.dev/Google (optional) |
| `openclaw/github-pat` | Push `factum_atlas.html` to repo |
| `openclaw/oracle-api-key` | Shared auth key between Oracle API and daatan |

### Bootstrap on an existing EC2 instance

```bash
# On the instance (via SSM session):
curl -sSL https://raw.githubusercontent.com/komapc/retro/main/infra/ec2_bootstrap.sh | bash

# Start pipeline loop
nohup bash ~/truthmachine/infra/ec2_run.sh \
  >> ~/truthmachine/pipeline_log.txt 2>&1 &
```

### Monitor from Local Machine
```bash
bash infra/monitor.sh
```

### Stop / Restart
```bash
# On EC2 (via SSM):
kill $(pgrep -f ec2_run.sh)

# Restart:
nohup bash ~/truthmachine/infra/ec2_run.sh >> ~/truthmachine/pipeline_log.txt 2>&1 &
```

---

## GitHub Actions

Workflow: `.github/workflows/deploy-atlas.yml`

Triggers on push to `main` when `factum_atlas.html` changes.
Deploys to **https://komapc.github.io/retro/**.

The EC2 pipeline commits and pushes `factum_atlas.html` after each cycle.

---

## Forecasting System Design

> Documented 2026-04-14 based on design conversation.

### Goal

Use the historical prediction+accuracy data to build a **media-weighted forecaster**:
given a new binary question, search the web for relevant articles, weight each source's
prediction by its historical accuracy on that topic, and output a calibrated probability
distribution.

### Data Requirements Added

1. **Event categories/tags** — every event gets one or more topic tags (multi-label).
   Used to compute per-source accuracy scores per topic.
2. **Author-level tracking** — predictions should be linked to author when available,
   enabling author-level accuracy scores within a source.

### Taxonomy (v1)

| Category | Example events |
|---|---|
| `Israeli Politics` | Coalition formation, judicial reform, elections |
| `Gaza War` | Oct 7, ground invasion, hostage deals, Rafah |
| `Regional Geopolitics` | Iran attack, Saudi normalization, ICJ ruling |
| `AI & Tech` | ChatGPT, GPT-4, DeepSeek, EU AI Act, Nvidia $1T |
| `Global` | Everything else |

Events can have multiple tags (e.g. Iran attack → `["Gaza War", "Regional Geopolitics"]`).
New categories can be added freely — the taxonomy is not fixed.

### Scoring Design

- **Confidence-weighted**: high-certainty predictions that turn out correct score more;
  high-certainty wrong predictions score worse. Formula TBD (Brier score already computed).
- **Two accuracy levels**: source-level and author-level, both per topic.
- **Binary outcomes only** for now; architecture should support continuous later.

### Inference Pipeline (future)

```
New question arrives
  │
  ├─ Match to topic category
  ├─ Search all sources for relevant articles (web_search.py)
  ├─ Extract predictions from articles (extractor.py)
  ├─ Look up each source's historical accuracy on that topic
  ├─ Weight predictions by source/author accuracy score
  └─ Aggregate → probability distribution (mean + confidence interval)
```

### ML Model Candidates (ranked by recommendation)

| # | Approach | Notes |
|---|---|---|
| 1 | **Weighted Bayesian Aggregation** | No training needed; Brier-score weights; interpretable |
| 2 | **Isotonic Regression Calibration** | Calibrate #1 against historical outcomes; corrects systematic bias |
| 3 | **Logistic Regression** | Features: source accuracy, certainty, days-before, stance, hedge_ratio |
| 4 | **Gradient Boosting (XGBoost/LightGBM)** | Captures non-linear interactions; best classical ML option |
| 5 | **Fine-tuned LLM Forecaster** | Article text → calibrated probability; highest ceiling, most expensive |

**Recommended path**: Start with #1+#2 → move to #4 once dataset is large enough → #5 long-term.

---

## Forecasting Microservice

> Phases 1–4 complete and live at `oracle.daatan.com`. Pending: daatan bot integration (Phase 5).

### Purpose

Given a binary question ("Will X happen by Y?"), return a calibrated probability distribution by searching current articles and weighting predictions by each source's historical accuracy on the relevant topic.

### Input / Output

```
POST /api/forecast
{
  "question": "Will Israel and Hamas reach a permanent ceasefire by June 2025?",
  "deadline": "2025-06-01",
  "async": false          // optional, default false
}

→ 200 OK
{
  "question": "...",
  "category": "Gaza War",         // auto-classified by LLM
  "mean": 0.38,
  "std": 0.14,
  "ci_low": 0.18,
  "ci_high": 0.58,
  "articles_found": 7,
  "articles_used": 5,
  "sources": [
    { "name": "Times of Israel", "trust": 0.84, "stance": 0.4, "certainty": 0.7 },
    ...
  ],
  "computed_at": "2026-04-14T12:00:00Z"
}
```

### Pipeline

**Stage 1 — Search & Fetch**
1. `web_search.search_articles(question, limit)` — SerpAPI → Serper.dev → Brave → DDG fallback chain
2. Per article: trafilatura full-text fetch (falls back to title+snippet)

**Stage 2 — Gatekeeper + Extractor** (parallel per article)
1. `gatekeeper.check_is_prediction()` — LLM filter: does this article contain a prediction?
2. `extractor.extract_predictions()` — LLM extraction: `stance`, `certainty`, `claim`, etc.

**Stage 3 — Weight by Source Credibility**
1. `leaderboard.get_credibility_weight(source_id)` — TrueSkill conservative score from `leaderboard.json`
2. `weight = credibility × certainty` per prediction

**Stage 4 — Aggregate → Distribution**
1. Weighted mean stance + variance → `{ mean, std, ci_low, ci_high }`
2. Convert to probability: `p = (mean + 1) / 2`

### Deployment (decided 2026-04-14)

**FastAPI microservice in `retro/api/`** — deployed as a second systemd service (`oracle-api.service`) on the retro EC2 alongside the batch pipeline.

- Imports `tm.gatekeeper`, `tm.extractor`, `tm.web_search` directly — no code ported
- Reads `leaderboard.json` from the same `data/` directory (refreshed every 5 min)
- Auth: `x-api-key` header + AWS Security Group (daatan SG → port 8001 only)
- Subdomain: `oracle.daatan.com`
- Test console: https://komapc.github.io/retro/oracle-test.html
- Full docs: `docs/ORACLE_API.md`

**Decisions closed:**
- Source scores stay in `leaderboard.json` on the retro EC2 (no daatan DB sync needed)
- TypeScript port rejected — pipeline is ~2000 lines of Python ML, porting is months of work

---

## Cost Estimates (at scale)

| Scale | LLM cost | Search | News licenses |
|---|---|---|---|
| Current (70 events × 12 sources) | ~$2 | $0 | $0 |
| 100 events × 20 sources, 6 months | ~$2–4 | $0 | $0 |
| 100 events × 100 sources, 10 years | ~$300–500 | $0 | $0–54K |

LLM cost is negligible. The real cost at scale is licensed news archive access.
