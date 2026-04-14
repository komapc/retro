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
├── pipeline/                    # Python pipeline (uv project)
│   ├── src/tm/
│   │   ├── gnews_ingest.py      # Article ingest: GNews RSS + multi-backend URL resolution + trafilatura
│   │   ├── gatekeeper.py        # LLM: does this article contain predictions?
│   │   ├── extractor.py         # LLM: extract structured predictions from article
│   │   ├── orchestrator.py      # Orchestrates ingest → extract → vault → atlas
│   │   ├── runner.py            # Runs gatekeeper + extractor per article
│   │   ├── render_atlas.py      # Renders factum_atlas.html from atlas/ data
│   │   ├── models.py            # Pydantic models (Prediction, ExtractionOutput, etc.)
│   │   ├── config.py            # Settings (models, API keys via .env)
│   │   ├── progress.py          # progress.json read/write helpers
│   │   ├── backtest.py          # LightGBM backtest + Polymarket comparison
│   │   └── scorer.py            # Brier score + calibration utilities
│   ├── scripts/
│   │   └── improve_keywords.py  # One-time: LLM-generate search keywords for events
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
│   ├── monitor.sh               # Local monitoring script (polls EC2 via SSM)
│   └── openclaw/terraform/      # Terraform for EC2 instance (us-east-1)
├── .github/workflows/
│   └── deploy-atlas.yml         # GitHub Actions: deploy factum_atlas.html to Pages
└── factum_atlas.html            # Generated atlas (committed by EC2 after each cycle)
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

### Prediction (extracted by LLM)
Each prediction has: `quote`, `claim`, `stance` (−1 to +1, event probability), `certainty`, `sentiment`, `specificity`, `hedge_ratio`, `conditionality`, `magnitude`, `time_horizon`, `prediction_type`, `source_authority`.

**stance** = how strongly the prediction implies the related event WILL occur.
- `+1.0` = author is certain the event will happen
- `−1.0` = author is certain the event will NOT happen
- `0.0`  = neutral / genuinely uncertain

---

## Pipeline Flow

```
gnews_ingest.py
  │  GNews RSS → titles in date window
  │  URL resolution chain: slug → Brave → SerpApi → Serper.dev → DDG
  │  trafilatura → clean article text  (fallback: BeautifulSoup)
  │  If 0 articles: CDX/Wayback fallback enumerates archived URLs
  │  Save to data/raw_ingest/{source}/{event}/article_NN.json
  ▼
orchestrator.py  (local_file mode)
  │  For each (event, source) cell not yet done:
  │    runner.py → gatekeeper.py (LLM: has predictions?)
  │                extractor.py  (LLM: extract structured predictions)
  │    Save extraction to vault2/extractions/{hash}_{event}_v1.json
  │    Save atlas link to atlas/{event}/{source}/entry_{hash[:8]}.json
  │    Update progress.json → status: done
  ▼
render_atlas.py
  │  Load all atlas/ entries
  │  Compute competitive Brier scores
  │  Render factum_atlas.html (interactive matrix)
  ▼
git push → GitHub Actions → GitHub Pages
```

---

## LLM Models

| Role | Model | Notes |
|---|---|---|
| Gatekeeper | `google/gemini-2.0-flash-lite-001` | Fast yes/no: does article contain predictions? |
| Extractor | `google/gemini-2.0-flash-lite-001` | Structured extraction of up to 10 predictions |
| Keywords | `google/gemini-2.0-flash-001` | One-time: generate search keywords per event |

All via OpenRouter. Change in `pipeline/src/tm/config.py`.

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

## Ingest Sources

| Source | Domain | Language |
|---|---|---|
| Times of Israel | timesofisrael.com | English |
| Jerusalem Post | jpost.com | English |
| Haaretz | haaretz.com | English |
| Reuters | reuters.com | English |
| Globes | en.globes.co.il | English |
| Ynet | ynetnews.com | English |
| Israel Hayom | israelhayom.com | English |
| Walla News | news.walla.co.il | Hebrew |
| N12 / Mako | www.mako.co.il | Hebrew |
| Maariv | www.maariv.co.il | Hebrew |
| Channel 13 | 13tv.co.il | Hebrew |
| Kan 11 | www.kan.org.il | Hebrew |

---

## Deployment

### Infrastructure
- **EC2**: `t4g.small`, Ubuntu, `eu-central-1` (Frankfurt)
- **Access**: AWS SSM Session Manager (no SSH key — instance has no key pair)
- **Instance name**: `truthmachine-pipeline` (`i-00ac444b94c5ff9b2`)
- **Public IP**: `3.120.185.111` (dynamic — reassigned on stop/start)
- **Terraform**: `infra/openclaw/terraform/`

### Required Secrets (AWS Secrets Manager, `us-east-1`)
| Secret name | Used by |
|---|---|
| `openclaw/openrouter-api-key` | LLM inference via OpenRouter |
| `openclaw/brave-api-key` | URL resolution — Brave Search (optional) |
| `openclaw/serpapi-key` | URL resolution — SerpApi/Google (optional) |
| `openclaw/serperdev-key` | URL resolution — Serper.dev/Google (optional) |
| `openclaw/github-pat` | Push `factum_atlas.html` to repo |

### Deploy to a New Server

```bash
# 1. Provision EC2 via Terraform
cd infra/openclaw/terraform
terraform init && terraform apply

# 2. Create required secrets in Secrets Manager
aws secretsmanager create-secret --region us-east-1 \
  --name openclaw/github-pat --secret-string "ghp_YOUR_TOKEN"
# (openrouter and brave keys should already exist)

# 3. Connect via SSM
aws ssm start-session \
  --target $(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=openclaw-worker" \
    --query "Reservations[0].Instances[0].InstanceId" --output text) \
  --region us-east-1

# 4. Bootstrap (run once on the instance)
curl -sSL https://raw.githubusercontent.com/komapc/retro/main/infra/ec2_bootstrap.sh | bash

# 5. Start pipeline loop
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

> Planned 2026-04-14. Not yet implemented.

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

**Stage 1 — Search & Extract**
1. Classify question into topic category using LLM (retro taxonomy: Israeli Politics, Gaza War, etc.)
2. Search for related articles via daatan's existing `searchArticles()` (6-provider chain)
3. For each article: run `gatekeeper.py` → `extractor.py` to get `stance`, `certainty`, `hedge_ratio`, etc.

**Stage 2 — Weight by Source Credibility**
1. Load `leaderboard.json` from retro (sync into daatan PostgreSQL nightly — see Open Decisions)
2. For each article's source: look up `weighted_brier_score` for the matched category
3. Compute trust weight: `weight = 1 / (weighted_brier + ε)` — lower Brier = higher trust

**Stage 3 — Aggregate → Distribution**
1. Each article contributes probability `p_i = (stance + 1) / 2`
2. Weight by `certainty × source_trust`
3. Compute weighted mean + variance → return `{ mean, std, ci_low, ci_high }`
4. Aggregation method: Weighted Bayesian (#1) initially → LightGBM (#4) when enough data

### Deployment Options (deferred)

| Option | Pros | Cons |
|---|---|---|
| **Python FastAPI microservice** | Reuses retro's extractor/gatekeeper/scorer/web_search directly | Extra service to maintain |
| **TypeScript routes in daatan** | Single deploy, reuses daatan's search chain | Must port Python ML logic |

**Recommendation:** Start as Python FastAPI — called via HTTP from daatan. Port later if needed.

### Open Decisions

| # | Question | Options |
|---|---|---|
| Q1 | Where do source scores live? | GitHub raw `leaderboard.json` vs daatan PostgreSQL (nightly sync recommended) |
| Q4 | Where does the service live? | Python FastAPI (recommended) vs daatan TypeScript routes |

---

## Cost Estimates (at scale)

| Scale | LLM cost | Search | News licenses |
|---|---|---|---|
| Current (30 events × 8 sources) | ~$0.50 | $0 | $0 |
| 100 events × 20 sources, 6 months | ~$2–4 | $0 | $0 |
| 100 events × 100 sources, 10 years | ~$300–500 | $0 | $0–54K |

LLM cost is negligible. The real cost at scale is licensed news archive access.
