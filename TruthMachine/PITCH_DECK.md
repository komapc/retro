# Retro Analysis (בדיעבד) — Seed Pitch Deck

> **Format:** 9 slides, narrative-first | **Stage:** Seed | **Last updated:** 2026-03-18

---

## Slide 1: Title

**Company:** Retro Analysis / בדיעבד

**One-liner:** *We measure who to trust. Then we predict.*

> _Visual: clean, dark background, company name + one-liner centered. No clutter._

---

## Slide 2: The Problem

**Israeli media shapes decisions — but no one measures if it was right.**

Every day, journalists, analysts, and commentators publish predictions about elections, wars, economic shifts, and diplomatic moves. Governments, funds, and enterprises make decisions based on this coverage.

But there is no score. No accountability. No way to know:
- Who called the Oct 7 threat before it happened?
- Which outlet predicted the Moody's downgrade — and which dismissed it as alarmist?
- Who has been systematically wrong about Iranian escalation for five years?

**Credibility is determined by reach, not by record.**

> _Visual: side-by-side — "What media says" vs "What actually happened." Simple, stark._

---

## Slide 3: The Solution

**We retroactively audit five years of Israeli and international media — and score every prediction.**

Using an LLM pipeline, we process thousands of articles, extract every forward-looking claim (explicit or implied), and score each one against what actually happened.

The result:
- A **competitive ranking** of journalists and outlets by domain — who is actually reliable on security, economics, politics
- A **credibility layer** for the information ecosystem, built on mathematical ground truth
- A **unique proprietary dataset** — thousands of scored predictions with verified outcomes, usable directly as source data and ground truth for ML model training. No one else has this.

This is **Retro Analysis (בדיעבד)** — the first system to close the loop between what was said and what was true.

> _Visual: simple pipeline diagram — Articles → Extract → Score → Rank → Dataset._

---

## Slide 4: The Secret (Our Unique Insight)

**Post-factum calibration is the moat.**

Everyone else measures sentiment in real time. We wait for reality to happen — then use it as a teacher.

Every historical event in our matrix is a labeled training example:
- We know what was predicted
- We know what actually occurred
- We can calculate exactly how wrong (or right) each source was

This generates something no competitor can buy: **a proprietary dataset of verified prediction accuracy going back five years**, across 125 events and 25 media sources.

Starting today, a competitor would need five years to replicate it.

We call this **Outcome-Supervised Narrative Calibration (OSNC)** — and it powers the second product.

> _Visual: timeline showing predictions made → outcomes verified → model trained. One clear flow._

---

## Slide 5: The Oracle (Product 2)

**Because we know who was right in the past, we can predict the future better than anyone.**

Once the historical matrix is built and sources are scored, we train a model on one question:

*Given who is saying what today — and how accurate they have historically been — what is the probability this event occurs?*

Output:
- `"Probability Netanyahu survives no-confidence vote: 0.83"`
- `"Likelihood of IDF ground operation in Lebanon within 30 days: 0.61"`
- `"Moody's second downgrade by Q2: 0.44"`

This is **TruthMachine** — a calibrated oracle API for geopolitical and economic events, sold to institutional clients.

> _Visual: large probability gauge at 0.76, surrounded by weighted source inputs._

---

## Slide 6: Traction

**The infrastructure is built. The first results are live.**

- ✅ Pipeline live: gatekeeper → forensic extractor → scoring (Hebrew + English)
- ✅ 125 seed events defined across 9 domains (politics, war, economy, tech, energy)
- ✅ 25 sources selected (15 Israeli, 6 international, Polymarket as auxiliary)
- ✅ **3 fully scored case studies published** — live at [komapc.github.io/retro](https://komapc.github.io/retro):
  - 🇻🇪 **Operation Absolute Resolve** — US capture of Maduro; Bloomberg & Reuters called it, ynet/Israel Hayom missed it
  - 📉 **Trump Trade Wars 2025** — tariff escalation & dollar decline; Haaretz called it, Calcalist dismissed it
  - ⚡ **Energy Volatility 2026** — European gas price spike; TheMarker called it, Globes missed it
- ✅ Repo public: github.com/komapc/retro

**Next milestone:** First 20 events × 25 sources fully scored and published.

> _Visual: screenshot of the live case study page — two columns (teal=accurate, rose=inaccurate), source quotes, outcome badge. Matrix grid with 3 cells filled._

---

## Slide 7: Business Model

**Freemium leaderboard → Institutional API**

| Tier | Product | Price |
|---|---|---|
| **Free** | Public credibility leaderboard (journalist & outlet scores) | $0 |
| **Pro** | Live Oracle API — probability estimates for current events | TBD |
| **Enterprise** | Full raw forensic data, custom domain scoring, white-label | TBD |

The free leaderboard drives awareness and positions us as the credibility standard.
The API is the revenue engine — sold to quant funds, prediction market traders, and government risk desks.

> _Visual: three-tier pricing table, clean._

---

## Slide 8: Market

**Who pays for better predictions about Israel and the Middle East?**

- **Quantitative funds & traders** — Israeli equities, FX, energy exposure; need edge over consensus
- **Prediction market participants** — Polymarket traders seeking data-driven advantage
- **Corporate & government risk desks** — geopolitical and supply chain scenario planning
- **Media & PR** — organizations wanting to benchmark their own credibility

The Israeli market is the proof of concept. The long-term ambition is to expand monitoring in every direction simultaneously:

- **More regions** — MENA, Eastern Europe, Gulf states, any high-stakes media ecosystem
- **More languages** — Arabic, Farsi, Turkish, Russian
- **More time** — historical archives going back decades, not just five years
- **More coverage** — eventually, every published article, not just event-centric sampling

This is feasible. The two-stage LLM pipeline (cheap filter → targeted extractor) keeps marginal cost per article near zero. The math scales linearly. With the right infrastructure, **total media coverage is not a moonshot — it is an engineering problem.**

> _Visual: concentric circles expanding outward — Israel → MENA → Global → All Languages → All Time._

---

## Slide 9: Team & The Ask

**Team**

*(Founders — to be completed)*

We are building at the intersection of investigative journalism, quantitative finance, and AI infrastructure. The product requires domain expertise in Israeli media, LLM pipelines, and calibrated probabilistic modeling.

---

**The Ask: $[X]**

| Use of funds | % |
|---|---|
| Data ingestion (Perigon / Event Registry) | 40% |
| LLM inference (OpenRouter) | 15% |
| Engineering (pipeline + API) | 35% |
| Legal & compliance | 10% |

**18-month goal:** 100×100 matrix complete, Oracle API in private beta, first paying institutional clients, provably beating market consensus on 3 major events.

> _Visual: simple pie chart + milestone timeline._

---

*"We measure who to trust. Then we predict."*
