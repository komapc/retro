# TruthMachine / Factum Atlas — Investment Plan

**Horizon: 12 months · Ceiling: ~$100,000**

---

## Part A — People

| Role | Type | Annual |
|---|---|---|
| Prediction Researcher — ML/NLP | Full-time | $65,000 |
| DevOps Engineer | Part-time contractor (~5 hrs/wk) | $15,000 |
| **People total** | | **$80,000** |

**Prediction Researcher** — Python, LLMs/fine-tuning, probability calibration, Bayesian scoring, NLP pipelines. *Project: build and train models for structured probability extraction from news; design scoring metrics for forecasting accuracy; run RetroAnalysis over 10-year Israeli media archive.*

**DevOps Contractor** — Terraform, EC2/RDS, GitHub Actions, nginx, systemd. *Project: manage CI/CD, scaling events, on-call infra.*

---

## Part B — Infrastructure

### 1. Production Platform — 100K users

Current stack (2× t3.small) will not survive 100K users. Needs:

| Resource | Spec | Annual |
|---|---|---|
| Application Load Balancer | ALB | ~$200 |
| App servers | 3× t3.large (auto-scaling group) | ~$2,700 |
| Database | RDS PostgreSQL db.t3.medium, Multi-AZ | ~$1,800 |
| Cache | ElastiCache Redis cache.t3.micro | ~$200 |
| CDN | CloudFront (static assets + API cache) | ~$300 |
| **Subtotal** | | **~$5,200/yr** |

> Existing daatan t3.smalls remain for staging.

---

### 2. ML Training — GPU Compute

For fine-tuning stance/extraction models on domain-specific data:

| Resource | Spec | Est. usage | Annual |
|---|---|---|---|
| EC2 g5.2xlarge | A10G GPU, 24 GB VRAM | ~600 GPU-hrs/yr spot | ~$250 |
| EC2 p3.2xlarge | V100, 16 GB VRAM | ~200 GPU-hrs/yr (large runs) | ~$180 |
| S3 — model checkpoints | Training artifacts | ~50 GB | ~$15 |
| **Subtotal** | | | **~$450/yr** |

> Spot instances cut GPU cost ~70% vs on-demand. Both instances can be provisioned on-demand for short bursts and terminated when done — no long-running GPU servers.

---

### 3. RetroAnalysis — 10-Year Israeli Media Archive

**Scope estimate:** ~50 major outlets (Haaretz, Ynet, Times of Israel, Jerusalem Post, Kan, i24, Walla, Maariv…) × ~30 articles/day × 10 years ≈ **5–7 million articles**.

| Phase | Resource | Cost |
|---|---|---|
| **Ingestion** | BrightData bulk scraping (one-time, ~6M pages) | ~$1,800 |
| **Storage** | S3 raw archive, ~200 GB | ~$55/yr |
| **Embeddings** | text-embedding-3-small, 6M articles × 500 tokens | ~$60 one-time |
| **LLM processing** | Gemini Flash gatekeeper + extractor, 6M articles | ~$450 one-time |
| **Vector index** | pgvector on existing RDS (no extra DB needed) | $0 |
| **Ongoing ingestion** | Daily delta crawl after backfill | ~$300/yr |
| **One-time backfill total** | | **~$2,300** |
| **Annual ongoing** | | **~$350/yr** |

> One-time backfill is the biggest single spend here. Spread over 2–3 months of processing, not a single bill.

---

### 4. Existing AWS Services (both repos)

From Terraform — already provisioned, cost continues:

| Service | Annual |
|---|---|
| EC2 t4g.medium (retro pipeline, us-east-1) | ~$480 |
| EC2 2× t3.small (daatan staging) | ~$480 |
| S3 — backups, uploads, mail, tf-state | ~$120 |
| SES + Lambda mail forwarder | ~$24 |
| Route53 (2 hosted zones) | ~$24 |
| ECR, Secrets Manager, CloudWatch, SNS | ~$240 |
| **Subtotal** | | **~$1,368/yr** |

---

### 5. Search APIs — 2 providers

| Provider | Role | Annual |
|---|---|---|
| Serper.dev Business | Primary — fast, reliable, 50K queries/mo | ~$1,800 |
| BrightData SERP | Fallback — paywalled + regional sources | ~$1,200 |
| **Subtotal** | | **~$3,000/yr** |

> DDG remains as free last resort. All other providers dropped.

---

### 6. LLM APIs — ongoing pipeline

| Provider | Use | Annual |
|---|---|---|
| OpenAI GPT-4o-mini | Oracle gatekeeper + extractor (production) | ~$1,800 |
| Google Gemini Flash | Bulk RetroAnalysis processing + research | ~$600 |
| **Subtotal** | | **~$2,400/yr** |

---

### 7. Monitoring & Tooling

| Tool | Plan | Annual |
|---|---|---|
| Grafana Cloud | Free tier (3 users, Loki logs, alerting) | $0 |
| Claude Code | Developer subscription | ~$240 |
| Domains, GitHub, misc | | ~$240 |
| **Subtotal** | | **~$480/yr** |

---

## Budget Summary

### People

| | Annual |
|---|---|
| ML/Research Engineer | $65,000 |
| DevOps contractor | $15,000 |
| **People total** | **$80,000** |

### Infrastructure

| | Annual | One-time |
|---|---|---|
| Production platform (100K users) | $5,200 | — |
| ML training GPU | $450 | — |
| RetroAnalysis pipeline | $350 | $2,300 |
| Existing AWS services | $1,368 | — |
| Search APIs | $3,000 | — |
| LLM APIs | $2,400 | — |
| Monitoring & tooling | $480 | — |
| **Infrastructure total** | **$13,248** | **$2,300** |

---

### Grand Total

| Category | Amount |
|---|---|
| People (12 months) | $80,000 |
| Infrastructure (12 months recurring) | $13,248 |
| RetroAnalysis backfill (one-time) | $2,300 |
| **Total** | **$95,548** |

**~$4,500 contingency** within the $100K ceiling for unexpected GPU spikes or a third engineering hire.
