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
  "llm_referee_criteria": "The Assad government loses effective control of Damascus."
}
```

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

## Cost Estimates (at scale)

| Scale | LLM cost | Search | News licenses |
|---|---|---|---|
| Current (30 events × 8 sources) | ~$0.50 | $0 | $0 |
| 100 events × 20 sources, 6 months | ~$2–4 | $0 | $0 |
| 100 events × 100 sources, 10 years | ~$300–500 | $0 | $0–54K |

LLM cost is negligible. The real cost at scale is licensed news archive access.
