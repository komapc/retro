# TruthMachine: Design Plan & Implementation Roadmap

> **Working name:** TruthMachine | **Status:** MVP Design v4 | **Last updated:** 2026-03-17

---

## 0. Product Vision

TruthMachine is a **B2B oracle SaaS** built on a retroactive media accuracy audit. It has two distinct outputs:

1. **Oracle API** — probability estimates for future events (e.g., `"Chances of Netanyahu winning elections: 0.76"`), sold via API to corporate clients, hedge funds, Polymarket traders, and government agencies.
2. **Media Reputation Rankings** — journalist and outlet accuracy scores (Brier Score, custom ELO variant). Free tier shows public leaderboard; paid tier gives raw data and full API access.

### Scoring Universe
All sources compete on the **same leaderboard** regardless of type: media outlets, wire services, financial institutions (Goldman Sachs, J.P. Morgan), think tanks (CSIS, Quincy Institute), bloggers, and independent analysts. Leveling the playing field is a core product differentiator.

### Proof of Concept
**Israel 2021–2026** is the first dataset. The long-term goal is to expand to other regions and time periods. Historical data ideally goes back to 2005 or earlier — sparse early coverage is acceptable and improves over time.

### Relation to Daatan
TruthMachine is a **fully separate product** — separate repo, separate DB, separate deployment. Future integration with Daatan Forecast (e.g., sharing reputation scores via API) is deferred.

---

## 1. Repository & Infrastructure

### Repository
- **Separate repo** from Daatan (e.g., `daatan-truthmachine`)
- Daatan's `retro/prototype/` stays in the Daatan repo as a UI reference/demo
- TruthMachine repo contains: Python pipeline, data files, documentation

### Storage Strategy
**Phase 1 (MVP) — Filesystem JSON:**
```
data/
  events/          # one JSON per event (ground truth, metadata)
  sources/         # one JSON per source (metadata, scores)
  matrix/          # one JSON per event+source pair (extracted predictions)
  pages/           # auto-generated per-event page data (consumed by UI)
```
~125 events × 25 sources = ~3,000 matrix files. Manageable, git-trackable, human-readable.

**Phase 2 — PostgreSQL** with `pgvector` + `TimescaleDB`, once the pipeline is proven to work. The JSON schema from Phase 1 maps directly to DB schema.

### Compute (AWS)
- **EC2 t4g.small** (2 vCPUs, 2 GiB RAM) — free-tier eligible until December 31, 2026
- Single Postgres instance sufficient for MVP; read replicas / dedicated vector DB added when needed

---

## 2. Source List

**25 sources total: 15 Israeli + 6 international + Polymarket (auxiliary data)**

See `sources.json` for the machine-readable list and `SOURCES.md` for selection criteria.

### Israeli Sources (15) — web only for MVP
Ynet, Haaretz, N12 (Mako), Israel Hayom, Globes, Kan 11, The Marker, Walla News, Maariv, Jerusalem Post, Times of Israel, Calcalist, Channel 13 News, Channel 14 (Now 14), Uri Kurlianchik (Substack)

### International Sources (6)
BBC News, Al Jazeera, CNN, Reuters, Bloomberg, Wall Street Journal

### TV & Media Handling
For TV sources (N12, Kan 11, etc.), the MVP strictly processes **written web articles** only. Video and audio ingestion (transcripts/CC) are deferred to Phase 2.

### Auxiliary
Polymarket — not a source, but `polymarket_prob` stored per prediction where a matching market exists. `NULL` when no market exists (expected for ~70% of Israeli events).

### Byline Handling
Store journalist byline when available. Score at outlet level only when byline is absent (wire services, unsigned editorials).

---

## 3. Event Seed List

**125 concrete binary events across 9 domains.** See `EVENTS.md` for the full list.

| Domain | Count |
|---|---|
| A — Israeli Politics & Elections | 25 |
| B — October 7 & Gaza War | 22 |
| C — Iran & Regional | 23 |
| D — Israeli Economy | 15 |
| E — Global Events | 10 |
| F — Israeli Society | 5 |
| G — Technology & AI | 10 |
| H — Israeli Tech & Cyber | 10 |
| I — Energy & Climate | 5 |

**Event selection criteria (MVP):**
- **Objective & Binary:** Only events that clearly "happened" or "didn't happen" (e.g., "Did law X pass the Knesset?").
- **Exclusions:** Vague or subjective events (e.g., "Did the protest movement succeed?") are excluded from the MVP.
- **Massive Coverage:** Event must have been widely reported after its occurrence.

---

## 4. Data Model: Predictions & Events

### Predictions
Each extracted prediction is stored as an **independent unit**. One article may produce multiple predictions (usually <= 3), each treated as a separate data point for the ML model.

| Field | Type | Description |
|---|---|---|
| `event_id` | string | Reference to seed event |
| `source_id` | string | Reference to source |
| `journalist` | string \| null | Byline if available |
| `article_url` | string | Source article |
| `article_date` | date | Publication date |
| `headline` | string | Article headline |
| `quote` | string \| null | Relevant extracted quote |
| `stance` | float (-1.0 to 1.0) | Directional outlook |
| `sentiment` | float (0.0 to 1.0) | Emotional tone |
| `certainty` | float (0.0 to 1.0) | Linguistic sureness |
| `specificity` | float (0.0 to 1.0) | How concrete the prediction is |
| `timing_stated` | bool | Did prediction specify a timeframe? |
| `polymarket_prob` | float \| null | Market probability at publication date |

### Event Metadata (Ground Truth)
To enable scoring and ingestion, each event requires:
- `outcome`: Boolean (True if event happened).
- `outcome_date`: The date the event was resolved.
- `search_keywords`: List of terms for article ingestion (Hebrew/English).
- `llm_referee_criteria`: Specific instructions to help LLM verify relevance.

---

## 5. LLM Pipeline & Prompt Strategy

Two-stage filtering pipeline via OpenRouter.

### Stage 1: The Gatekeeper
- **Model:** Nemotron 3 Nano (free / ultra-low cost)
- **Task:** Does this snippet contain a forward-looking prediction?
- **Output:** `{"is_prediction": boolean, "reason": string}`

### Stage 2: Forensic Extraction
- **Model:** DeepSeek V3.2 ($0.25/1M input tokens)
- **Task:** Extract structured prediction metrics into Pydantic schema (via `instructor`).
- **Context:** The LLM is provided with the specific `event_name` and `event_description` to focus extraction on relevant predictions.
- **Output:** Full prediction JSON.

### Logic Refinements
- **Event-wise Iteration:** The pipeline iterates by event. Articles may be processed multiple times if relevant to multiple events.
- **Independent Voices:** Article deduplication is not performed; wire stories are treated as independent "voices" for the outlet that chooses to publish them (often with added analysis).
- **Publication Window:** **CRITICAL.** Only articles published *before* the event's `outcome_date` are processed.

---

## 6. Python Pipeline Stack

The pipeline is a **standalone Python service** in the TruthMachine repo.

| Layer | Tool | Reason |
|---|---|---|
| HTTP fetching | `httpx` + `asyncio` | Async parallel article fetching |
| LLM calls | `litellm` | Unified interface to OpenRouter/any model |
| Structured extraction | `instructor` | Forces LLM output into Pydantic schemas |
| Data validation | `Pydantic v2` | Schema enforcement throughout |
| Database (Phase 2) | `SQLAlchemy` async + `asyncpg` | Async Postgres |
| Scheduling | `APScheduler` | Simple cron-like scheduling, no Redis needed |
| Package manager | `uv` | Fast, modern |
| Testing | `pytest` + `pytest-asyncio` | Standard |

---

## 7. Output: Per-Event Pages

The pipeline **automatically generates** a per-event page data file in `data/pages/` for every event.

Page structure:
- Two-column verdict: accurate sources (YES) vs. inaccurate sources (NO)
- Source name, headline, date, extracted quote
- Detailed analysis section
- Citations

---

## 8. Scoring & Reputation System

### Scoring tracks
- **Journalist score** — follows the person across outlets.
- **Outlet score** — publication's aggregate accuracy.

### Scoring methods
- **Brier Score:** Primary calibration metric.
- **ELO Rating:** Zero-sum relative rank.
- **No Manual Formula:** The ML model will learn the optimal weights for `stance`, `certainty`, `specificity`, etc., to derive the final probability used for Brier scoring.

---

## 9. Oracle Model

Generates probability estimates by aggregating predictions weighted by source reputation.
- **ML Model:** Learns the relationship between extraction metrics and actual outcomes.
- **Data Density:** Handling of sparse data (low vs. high volume) to be decided in a later phase.

---

## 10. API Design

| Endpoint type | Description |
|---|---|
| Event probability | `"What is the probability of X?"` |
| Journalist reputation | Score, domain breakdown, history |
| Outlet reputation | Same at outlet level |

---

## 11. Cost & Time Estimation (MVP)

| Component | Provider | Estimated Cost |
|---|---|---|
| News Ingestion | TBD (Perigon / Event Registry / Custom) | $90 – $550/mo |
| LLM Inference | OpenRouter (blended) | ~$25 |
| AWS Hosting | t4g.small (free tier) | $0 |

---

## 12. Open Problems & Deferred Decisions

| # | Problem | Status |
|---|---|---|
| 1 | Ingestion Provider Selection | **PENDING** |
| 2 | Oracle ML model architecture | Deferred |
| 3 | Exact ELO formula | Deferred |
| 4 | Oracle Confidence/Density Score | Deferred |
| 5 | Telegram/video ingestion | Phase 2 |
| 6 | Journalist identity merging | Phase 2 |
| 7 | Legal Review | **CRITICAL** |

---

*First priority: Populate `EVENTS.md` metadata (outcome, dates, keywords).*
