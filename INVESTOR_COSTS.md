# TruthMachine / Factum Atlas — Investor Budget

**Two sequenced stages over 18 months.** Stage 1 builds the MVP and ships Daatan Forecast; Stage 2 covers the baseline cost of operating it at 100K users with production-grade infrastructure.

| Stage | Period | Headline cost | Primary outcome |
|---|---|---|---|
| 1 — MVP build | Months 1–6 | **$262,000** | 100×200 ME matrix, 5+ years retro fill, Daatan Forecast Android (target 200k MAU) |
| 2 — Scale baseline | Months 7–18 | **$183,370** ($180K recurring + $3,370 one-time) | Multi-AZ HA infra, ML training capacity, oracle pipeline at scale |
| **Total ask** | **18 months** | **~$445,370** | |

> **Relationship to MVP_PLAN_6M.md.** That document describes an *aggressive* Months 7–18 plan — "Phase 2 — Worldwide Expansion" at ~$1M (Series A) targeting 5 regions and 10M MAU. The Stage 2 figure here is the **conservative operating baseline** for the same window: what it costs to keep the MVP running at 100K users without the worldwide push. They are two different scenarios for the same period, not duplicate accounting.

> **Team-composition note.** Stage 1 personnel ($245.7K) covers two full-salary founders plus a math hire — the build cost. Stage 2 personnel ($80K) adds an ML researcher and a part-time DevOps contractor; founder salaries in Stage 2 are assumed covered by follow-on funding or revenue and are **not** included in the $183.37K figure.

> **User-base-figure note.** Stage 1 targets **200k MAU** for Daatan Forecast (a consumer Android app — most usage is read-only / cached). Stage 2 sizes infrastructure for **100K total users** (~7K DAU, per the search-volume model in §6 of Stage 2) hitting the oracle pipeline at typical write/inference rates. The Stage 2 figure is the binding constraint on infra spend; the larger MAU figure is consistent because most of Daatan's surface is pre-computed.

---

# Stage 1 — MVP Build (Months 1–6, $262,000)

**Scope:** 100×200 Middle East matrix, 5+ years retro fill + Daatan Forecast Android app targeting 200k MAU.
**Assumptions:** Israel-based team, zero revenue, promotion excluded, AWS infrastructure.

## 1. Personnel

Three people: 2 founders (full market salary) + 1 mathematician / data engineer (new hire).

| Role | Arrangement | NIS/mo | Duration | Total |
|---|---|---|---|---|
| Founder × 2 | Employee | 45,000 each = 90,000 | 6 months | ~₪691,000 (~$186,800) incl. employer costs |
| Math consultant | Freelance | ~15,000 | Months 1–3 | ~₪45,000 (~$12,200) no employer costs |
| Mathematician (full hire) | Employee | 45,000 | Months 4–6 | ~₪173,000 (~$46,700) incl. employer costs |
| **Total personnel** | | | | **~$245,700** |

> Mathematician engaged as a paid consultant in months 1–3 (feature design, model architecture) then transitions to full-time employee from month 4.
> Israeli employer costs include bituach leumi, pension (6.5%), advanced training fund (7.5%).
> Exchange rate assumed: ₪3.7 = $1.

## 2. Paid content access — archives, paywalls, licensing

~20 of 100 sources require paid access (Haaretz archive, Calcalist, Globes, key Arabic sources).
CDX/Wayback covers the remaining ~80% for historical content.

| Item | Cost (1-month subscription, scrape & cancel) |
|---|---|
| Haaretz digital archive | $150–300 |
| Hebrew business press (Globes, Calcalist) | $100–200 |
| Arabic source archives (2–3 key outlets) | $100–300 |
| Contingency (additional sources) | $150–400 |
| **Total** | **$500–1,200** |

> One month only — subscribe, run retro scrape, cancel. No ongoing commitment.

## 3. Cloud infrastructure (AWS)

Currently <$100/mo. Scales with Daatan Forecast user growth.

| Period | Monthly | Total |
|---|---|---|
| Months 1–3 (build + small user base) | ~$250–400 | ~$900 |
| Months 4–6 (scaling to 200k MAU) | ~$600–1,200 | ~$2,400 |
| **Total 6 months** | | **$3,000–5,500** |

> Includes EC2 (pipeline + API), RDS, S3, CloudFront, load balancer.
> At 200k MAU the app is read-heavy with pre-computed data — manageable on 2–3 mid-range instances.

## 4. LLM API cost (retro fill + ongoing)

Pipeline uses Gemini 2.0 Flash Lite via OpenRouter (~$0.075/1M input tokens).

| Item | Estimate |
|---|---|
| Retro fill: 20,000 cells × ~10 articles, gatekeeper + extractor passes | ~$200–400 one-time |
| Ongoing monthly (new events, rescoring) | ~$50–100/mo → ~$300 over 6 months |
| **Total** | **~$500–700** |

> This is the cheapest line item. Gemini Flash Lite makes LLM costs almost negligible at this scale.

## 5. Translation infrastructure (Google Translate API)

Arabic + Turkish for MVP. Extraction is done in English post-translation.

| Item | Estimate |
|---|---|
| Retro fill: ~30% of sources × 200k articles × ~5,000 chars | ~$4,000–7,000 one-time |
| Ongoing monthly | ~$200–400/mo → ~$1,200 over 6 months |
| **Total** | **$5,000–8,500** |

## 6. Legal / IP counsel + incorporation

Company not yet incorporated.

| Item | Cost |
|---|---|
| Israeli company incorporation (lawyer + gov fees) | $1,500–3,000 |
| App ToS, privacy policy, data processing agreements | $1,500–3,500 |
| Light ongoing counsel (scraping ToS review, licensing) | $500–1,000/mo → $2,000–4,000 |
| **Total** | **$5,000–10,500** |

## 7. Prediction market & financial data feeds

Polymarket currently scraped free. Minimal additional feeds needed for ME matrix.

| Item | Cost |
|---|---|
| Licensed / stable data feeds (contingency) | $500–2,000 |
| **Total** | **$500–2,000** |

## 8. Promotion / campaign

**Excluded from this estimate.** Viral growth assumed for Daatan Forecast.

## Stage 1 — Consolidated Budget

| Category | Low | High |
|---|---|---|
| Personnel (2 founders 6mo + consultant 1–3 + engineer 4–6) | $245,700 | $245,700 |
| Paid content access (1-month scrape) | $500 | $1,200 |
| Cloud infrastructure (AWS) | $3,000 | $5,500 |
| Translation API | $5,000 | $8,500 |
| Legal / incorporation | $5,000 | $10,500 |
| LLM API (Gemini Flash Lite) | $500 | $700 |
| Data feeds | $500 | $2,000 |
| **Total** | **$255,000** | **$268,000** |

**Working figure: ~$262,000 for 6 months.**

> At ₪45,000 founder salaries this exceeds the YC $125k program. Suitable for a pre-seed or angel round, or YC standard batch ($500k for 7%).

## Stage 1 — Key observations

1. **Personnel is 85–90% of total cost.** Everything else is noise by comparison.
2. **LLM costs are negligible** — Gemini Flash Lite at $0.075/1M tokens makes the pipeline economics extremely favorable.
3. **Translation is the #2 technical cost**, not LLM inference. Arabic/Turkish retro fill at scale costs more than all LLM calls combined.
4. **Content access risk is real** — 83% of current test cells return no predictions, partly due to paywall gaps in Wayback. Budget ~$3–8k to patch the worst offenders.
5. **Viral assumption is load-bearing** — if Daatan Forecast does not grow organically, the $0 promotion budget means the 200k MAU target is unachievable without additional spend.

---

# Stage 2 — Scale Baseline (Months 7–18, $183,370)

**Horizon:** 12 months · **People ceiling:** $80K · **Infrastructure ceiling:** $100K · **One-time backfill:** $3,370

## Part A — People (Stage 2)

| Role | Type | Annual |
|---|---|---|
| Prediction Researcher — ML/NLP | Full-time | $65,000 |
| DevOps Engineer | Part-time contractor (~5 hrs/wk) | $15,000 |
| **People total** | | **$80,000** |

**Prediction Researcher** — Python, LLMs/fine-tuning, probability calibration, Bayesian scoring, NLP pipelines.
*Project: train models for structured probability extraction from news; design scoring metrics; run RetroAnalysis over 10-year Israeli media archive.*

**DevOps Contractor** — Terraform, EC2/RDS, GitHub Actions, nginx, systemd.
*Project: maintain CI/CD, manage scaling events, on-call infra support.*

> Founder salaries continue from Stage 1 but are assumed covered by follow-on funding or initial revenue and are **not** included in this $80K figure.

## Part B — Infrastructure (Stage 2)

> **Current state:** PostgreSQL runs inside Docker on a single t3.small with no dedicated DB server, no Multi-AZ, no load balancer, and no Redis. This is fine for hundreds of users but collapses under 100K.

### 1. Compute — Production (100K users)

Current setup has one public subnet in one AZ — any instance failure takes the site down. At scale:

| Resource | Spec | Annual |
|---|---|---|
| Application Load Balancer | ALB across 2 AZs | ~$600 |
| App servers — auto-scaling group | 4–8× c6g.large (avg 5), 2 AZs | ~$6,200 |
| NAT Gateways | 2× (one per AZ, required for private subnets) | ~$800 |
| Elastic IPs, VPC endpoints | | ~$200 |
| **Subtotal** | | **~$7,800/yr** |

> ⚠️ **Risk — traffic spike:** A viral news event (war, election) can push 10× normal traffic in minutes. Auto-scaling group max capacity needs headroom. Burst cost: up to $2,000 in a single bad week.

### 2. Database — Move from Docker to Managed RDS

PostgreSQL currently runs in Docker on the same t3.small as the app. No connection pooling, no read replicas, no automatic failover. **One corrupted volume = total data loss.**

| Resource | Spec | Annual |
|---|---|---|
| RDS PostgreSQL — primary | db.r6g.large (2 vCPU, 16 GB RAM), Multi-AZ | ~$3,650 |
| RDS — read replica | db.r6g.large (offload analytics + leaderboard queries) | ~$1,825 |
| Extended backup retention | 35 days PITR + cross-region snapshot | ~$400 |
| Performance Insights + Enhanced Monitoring | | ~$200 |
| **Subtotal** | | **~$6,075/yr** |

> ⚠️ **Risk — data growth:** 100K users × years of predictions + RetroAnalysis articles = DB could hit 500 GB. r6g.large has 128 GB max storage before needing a larger instance class (db.r6g.xlarge = double cost ~$7,300/yr Multi-AZ).

> ⚠️ **Risk — connection exhaustion:** Next.js serverless routes open a new DB connection per request. At scale this hits PostgreSQL's connection limit hard — needs PgBouncer or RDS Proxy ($0.015/hr = ~$130/mo = **$1,560/yr** extra).

### 3. Cache — Redis

No Redis today. Every leaderboard render, every credibility score lookup, every session check hits the DB directly.

| Resource | Spec | Annual |
|---|---|---|
| ElastiCache Redis — clustered | cache.r6g.large, 2 nodes (primary + replica) | ~$3,300 |
| **Subtotal** | | **~$3,300/yr** |

> ⚠️ **Risk:** Redis is also the rate-limiter for oracle API. If it goes down, rate limiting fails open → uncontrolled LLM/search spend until restarted.

### 4. ML Training — GPU Compute

Training custom stance/extraction models on domain-specific geopolitical text requires serious GPU:

| Resource | Spec | Use | Annual |
|---|---|---|---|
| EC2 p4d.24xlarge (spot) | 8× A100 80 GB, ~$10/hr spot | Full model training runs, ~300 hrs | ~$3,000 |
| EC2 g5.12xlarge (spot) | 4× A10G 24 GB, ~$1.70/hr spot | Experiments, fine-tuning, eval | ~$2,900 |
| EFS | 1 TB (shared training dataset) | Training data mount | ~$360 |
| S3 | 1 TB (checkpoints + artifacts) | Model versioning | ~$276 |
| **Subtotal** | | | **~$6,536/yr** |

> ⚠️ **Risk — experiment sprawl:** Hyperparameter search, ablation studies, failed runs. A single poorly supervised training campaign can burn 3–5× the planned GPU budget in a week. Actual range: **$6K–$20K/yr** depending on research intensity.

> ⚠️ **Risk — model size creep:** If the researcher decides a 13B or 70B fine-tune is necessary, training costs multiply 5–10×. p4d.24xlarge spot is ~$10/hr — a 3-day training run = $720.

### 5. RetroAnalysis — 10-Year Israeli Media Archive

**Scope:** ~50 major outlets (Haaretz, Ynet, Times of Israel, Jerusalem Post, Kan, i24, Walla, Maariv, Calcalist…) × ~30 articles/day × 10 years ≈ **6–8 million articles**.

| Item | Resource | Cost |
|---|---|---|
| **One-time ingestion** | BrightData bulk scraping, ~7M pages | ~$2,800 |
| **One-time embeddings** | text-embedding-3-small, 7M articles × 500 tokens | ~$70 |
| **One-time LLM processing** | Gemini Flash, gatekeeper + extractor × 7M | ~$500 |
| **Vector database** | Pinecone Professional, 7M vectors × 1536 dims | ~$3,000/yr |
| **S3 raw archive** | ~300 GB text + metadata | ~$84/yr |
| **Ongoing delta crawl** | Daily ingest of new articles, BrightData | ~$600/yr |
| **Annual re-embedding** | Model upgrades trigger re-index | ~$500 |
| **One-time total** | | **~$3,370** |
| **Annual ongoing** | | **~$4,184/yr** |

> ⚠️ **Risk — scope expansion:** "Israeli media" likely expands to Arabic-language regional media, international coverage of Israel, or a second country entirely. 7M → 50M articles = Pinecone costs scale to $25K+/yr or require self-hosted Weaviate on a dedicated server (~$2,400/yr EC2).

> ⚠️ **Risk — scraping blocks:** Israeli news sites (especially Haaretz, paywalled) actively block scrapers. BrightData may require premium residential proxies ($3–5× more expensive) for paywalled content.

### 6. Search APIs — Scaled for 100K Users

This is the **fastest-growing cost** at scale. The oracle runs searches for every forecast request.

**Volume estimate:**
- 100K users, 7% DAU = 7,000 daily active
- 3 oracle calls/user/day = 21,000 oracle calls/day
- 5 searches/oracle call = **105,000 searches/day = 3.15M/month**

| Provider | Role | Annual |
|---|---|---|
| Serper.dev Enterprise | Primary (~3M queries/mo, negotiated rate) | ~$12,000 |
| BrightData SERP | Fallback (~500K queries/mo, $0.002/query) | ~$12,000 |
| **Subtotal** | | **~$24,000/yr** |

> ⚠️ **Risk — BrightData cost:** BrightData SERP pay-as-you-go hits hard at volume. 500K queries/mo × $0.002 = $1,000/mo. Negotiate a flat monthly contract early.

> ⚠️ **Risk — geopolitical spike:** A major Middle East event (war escalation, election) drives a sudden 5–10× search spike in a single day. At $0.002/query, 1M queries in 24 hours = $2,000 in one day — with no automatic spend cap unless WAF/rate-limiting is in place.

> ⚠️ **Risk — Serper quota exhaustion:** Happened once already (April 2026). At enterprise scale, a single bad day of scraping can exhaust the monthly quota. Need prepaid buffer or auto-downgrade to BrightData.

### 7. LLM APIs — Oracle Pipeline at Scale

At 21,000 oracle calls/day, each running gatekeeper + extractor on 5 articles:
= 210,000 LLM calls/day × 1,000 tokens avg = **210M tokens/day = 6.3B tokens/month**

| Provider | Use | Monthly | Annual |
|---|---|---|---|
| OpenAI GPT-4o-mini | Oracle gatekeeper + extractor | ~$1,100 | ~$13,200 |
| OpenAI GPT-4o | Hard questions (est. 10% of calls) | ~$500 | ~$6,000 |
| Google Gemini Flash | RetroAnalysis bulk + research | ~$100 | ~$1,200 |
| **Subtotal** | | **~$1,700/mo** | **~$20,400/yr** |

> ⚠️ **Risk — model upgrade:** If the researcher determines that GPT-4o-mini quality is insufficient for accurate extraction and 50% of calls must use GPT-4o ($2.50/1M input, $10/1M output), the LLM bill doubles to **$40K+/yr**.

> ⚠️ **Risk — context window growth:** Adding more articles per oracle call (from 5 to 10), longer snippets, or chain-of-thought prompting → token count per call doubles, cost doubles.

### 8. Storage, CDN & Egress

Often overlooked — AWS charges for data leaving the network.

| Resource | Spec | Annual |
|---|---|---|
| S3 (all buckets, ~1 TB at scale) | Backups, uploads, archives, tf-state | ~$280 |
| EBS snapshots (database + EC2) | ~200 GB/mo retained | ~$360 |
| CloudFront CDN | ~10 TB/mo served to 100K users | ~$1,020 |
| EC2 → Internet egress | ~50 GB/day not covered by CloudFront | ~$1,620 |
| Cross-AZ traffic | Multi-AZ DB + Redis replication | ~$300 |
| **Subtotal** | | **~$3,580/yr** |

> ⚠️ **Risk — egress surprise:** AWS egress ($0.09/GB) is a silent killer. A single feature that sends large article bodies to the client instead of summaries can multiply egress 10×. CloudFront must be in front of all content delivery.

### 9. Security

| Resource | Annual |
|---|---|
| AWS WAF (web ACL + managed rule groups) | ~$600 |
| AWS Shield Advanced (DDoS — prediction markets are targets) | ~$3,000 |
| Annual penetration test (third party) | ~$4,000 |
| **Subtotal** | **~$7,600/yr** |

> ⚠️ **Risk — prediction market DDoS:** Forecasting platforms are targets for manipulation attacks (flood the oracle with requests to exhaust quotas right before an event). Shield Advanced is not optional at 100K users.

### 10. Observability & On-call

| Tool | Plan | Annual |
|---|---|---|
| Grafana Cloud Pro | 10 users, 30-day retention, Loki + Prometheus | ~$350 |
| AWS CloudWatch enhanced + log retention | App logs, RDS metrics, Lambda logs | ~$600 |
| AWS X-Ray | Distributed tracing across oracle + daatan | ~$300 |
| PagerDuty | 2 on-call users, incident routing | ~$576 |
| **Subtotal** | | **~$1,826/yr** |

### 11. AWS Support

At ~$5K/mo AWS bill, Business Support is necessary (access to Cloud Support engineers within 1 hour for production incidents):

| | Annual |
|---|---|
| AWS Business Support (~10% of monthly bill) | ~$5,000 |
| **Subtotal** | **~$5,000/yr** |

### 12. Existing Services (Terraform — both repos)

Already provisioned, cost continues unchanged:

| Service | Annual |
|---|---|
| EC2 t4g.medium (retro pipeline, us-east-1) | ~$480 |
| EC2 2× t3.small (daatan staging, eu-central-1) | ~$480 |
| SES + Lambda mail forwarder | ~$24 |
| Route53 (3 hosted zones) | ~$36 |
| ECR (container registry) | ~$120 |
| Secrets Manager (~30 secrets) | ~$150 |
| Lambda (cron functions) | ~$60 |
| SNS | ~$60 |
| GitHub Team + Actions minutes | ~$480 |
| Claude Code subscription | ~$240 |
| Domain names | ~$120 |
| **Subtotal** | **~$2,250/yr** |

## Stage 2 — Infrastructure Budget Summary

| Category | Annual | One-time |
|---|---|---|
| Compute — production (HA, multi-AZ) | $7,800 | — |
| Database — RDS Multi-AZ + read replica | $6,075 | — |
| Cache — Redis clustered | $3,300 | — |
| ML Training — GPU | $6,536 | — |
| RetroAnalysis pipeline | $4,184 | $3,370 |
| Search APIs (3M queries/mo) | $24,000 | — |
| LLM APIs (oracle at scale) | $20,400 | — |
| Storage, CDN, egress | $3,580 | — |
| Security (WAF + Shield + pentest) | $7,600 | — |
| Observability + on-call | $1,826 | — |
| AWS Support (Business) | $5,000 | — |
| Existing services & tooling | $2,250 | — |
| **Infrastructure recurring** | **$92,551** | **$3,370** |
| **Contingency (8%)** | **$7,449** | — |
| **Infrastructure total** | **$100,000** | **$3,370** |

## Stage 2 — Cost Overrun Scenarios

| Scenario | Probability | Extra cost |
|---|---|---|
| Search spike during geopolitical event (1M queries in 48hrs) | High | +$2,000 one-time |
| LLM upgrade from GPT-4o-mini → GPT-4o for quality | Medium | +$20,000/yr |
| DB scale-up needed (r6g.large → r6g.2xlarge) | Medium | +$3,600/yr |
| RetroAnalysis expands to 2nd country (50M articles) | Medium | +$18,000/yr vector DB |
| ML training experiment sprawl (3× planned GPU hrs) | High | +$13,000/yr |
| BrightData no enterprise deal (pay-as-you-go) | Low | +$10,000/yr |
| DDoS attack without Shield Advanced | Low | +$15,000 incident |
| RDS Proxy needed for connection pooling | Medium | +$1,560/yr |

## Stage 2 — Grand Total

| Category | 12-month |
|---|---|
| People | $80,000 |
| Infrastructure (recurring) | $100,000 |
| RetroAnalysis backfill (one-time) | $3,370 |
| **Total** | **$183,370** |

> People and infrastructure are roughly equal at scale — this is typical for AI-heavy products where compute is the second headcount.

---

# Combined 18-Month Ask

| Stage | Period | Total |
|---|---|---|
| Stage 1 — MVP build | Months 1–6 | $262,000 |
| Stage 2 — Scale baseline | Months 7–18 | $183,370 |
| **Combined ask** | **18 months** | **~$445,370** |

*Promotion, revenue model, and valuation are addressed separately.*
