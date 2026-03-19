# Bediavad — Competitive Analysis

> Last updated: 2026-03-19

---

## Our Position in One Sentence

**TipRanks for geopolitical media × Good Judgment for the Middle East.**

No existing competitor combines retroactive outcome-based prediction scoring of journalists and media outlets with a public calibrated probability API for geopolitical events.

---

## The Two Dimensions

Bediavad operates across two distinct product dimensions. Competitors exist in each, but none span both:

| Dimension | What we do | Closest competitor |
|---|---|---|
| **Retroactive scoring** | Score every journalist/outlet prediction against what actually happened | TipRanks (finance only) |
| **Calibrated oracle API** | Output probability estimates for current geopolitical events | Good Judgment / Metaculus |

---

## Competitor Profiles

### 1. TipRanks
**Category:** Financial analyst performance tracking
**Description:** Tracks and ranks 96,000+ Wall Street analysts, bloggers, hedge fund managers, and insiders. Scores every recommendation against actual stock performance since 2009. Methodology developed with Cornell (success rate, average return, statistical significance).
**Pricing:** Free tier. Premium ~$29.95/month.
**Similarities to Bediavad:** Closest structural analog — retroactive scoring of predictions against outcomes, journalist/analyst-level granularity, calibration over time.
**Differences:** Finance only (stock picks). No geopolitical domain. No oracle API. No Hebrew/Israeli coverage.
**Threat level:** Low — different domain. High — proof that the model works and people pay for it.

---

### 2. Seeking Alpha
**Category:** Financial media + analyst tracking
**Description:** 7M+ registered users. Tracks 10,000+ financial analysts and bloggers. Scores contributors on success rate, average return, and statistical significance (Cornell methodology). Also provides Quant Ratings for stocks.
**Pricing:** Free tier. Premium ~$19.99/month. Pro ~$199.99/year.
**Similarities:** Retroactive prediction scoring, analyst ranking by domain accuracy.
**Differences:** Finance only. No geopolitical or political predictions. No oracle API.
**Threat level:** Low — different domain. Useful as a pricing benchmark ($299/year is aligned with their model).

---

### 3. Good Judgment Inc. / Superforecasting
**Category:** Expert calibrated forecasting
**Description:** Commercial spin-off of the IARPA Good Judgment Project. Deploys ~180 curated "Superforecasters" to produce calibrated probability estimates for enterprise clients. FutureFirst product provides daily-updated probability streams with API access.
**Pricing:** Not public. Enterprise contracts, estimated high five figures/year.
**Similarities:** Calibrated probability API, Brier-score methodology, geopolitical domain.
**Differences:** Human-panel based (not media-derived). Does not score journalists or outlets. Does not focus on Israeli/Middle East media ecosystem. Very expensive.
**Threat level:** High on oracle side — credible, proven, institutional clients.

---

### 4. Metaculus
**Category:** Community forecasting platform
**Description:** Nonprofit-backed platform where thousands of forecasters track and resolve probabilistic predictions. Full Brier-score calibration tracking per forecaster. API v2.0 available.
**Pricing:** Free for community. Enterprise/research contracts custom.
**Similarities:** Calibrated probability estimates, resolution tracking, open API.
**Differences:** Crowd-sourced (not media-derived). Does not score journalists. Geopolitics is one of many domains, not the focus.
**Threat level:** Medium — same output format as our oracle, but different methodology and data source.

---

### 5. Hypermind
**Category:** Enterprise crowd forecasting
**Description:** French firm combining crowd forecasting + AI "Forecasting Machine." Clients include EDF, OECD, Swedish government. Uses Brier scores. Has received Open Philanthropy grants.
**Pricing:** Enterprise only; not public.
**Similarities:** Calibrated oracle for institutional clients, Brier-score methodology.
**Differences:** Human crowd, not media-derived. No journalist scoring. European focus.
**Threat level:** Medium — credible with government clients.

---

### 6. Eurasia Group
**Category:** Political risk consultancy
**Description:** World's largest political risk consultancy (Ian Bremmer). Qualitative country-by-country risk analysis, annual "Top Risks" reports, bespoke advisory. Revenue ~$33M/year.
**Pricing:** Enterprise retainers, estimated low-to-mid six figures.
**Similarities:** Same buyer persona (funds, governments, corporates seeking geopolitical intelligence).
**Differences:** Qualitative narrative, not quantified probabilities. No prediction scoring. No outcome tracking. Much more expensive.
**Threat level:** Low on product — but occupies the same budget line. We are a cheaper, more accountable alternative.

---

### 7. Oxford Analytica
**Category:** Political intelligence
**Description:** Founded 1975, acquired by Dow Jones (February 2025). Daily Brief covering 250+ issues across 130 countries. Global Risk Monitor. Expert analyst network of 1,400+.
**Pricing:** Enterprise only; not public.
**Similarities:** Geopolitical intelligence for institutional clients.
**Differences:** Qualitative, narrative-only. No prediction accuracy tracking. No probability API.
**Threat level:** Low on product. Medium on brand — Dow Jones acquisition gives them significant distribution.

---

### 8. Stratfor / RANE Network
**Category:** Geopolitical analysis
**Description:** RANE acquired Stratfor in 2020. Worldview provides geopolitical analysis and country risk monitoring. Individual reports at $49–$99. Professional subscriptions from ~$7/week.
**Pricing:** Individual from ~$7/week. Enterprise custom.
**Similarities:** Geopolitical intelligence product, overlapping buyer persona.
**Differences:** Narrative analysis, no calibration, no prediction scoring, no oracle API.
**Threat level:** Low.

---

### 9. NewsGuard
**Category:** Media reliability ratings
**Description:** Trained journalists rate 35,000+ news sources on 9 apolitical journalistic criteria (accuracy, transparency, sourcing, corrections policy, etc.). Produces 0–100 trust score per outlet. Consumer browser extension + enterprise API.
**Pricing:** Consumer: $4.95/month. Enterprise: custom API/datastream.
**Similarities:** Media outlet credibility scoring, enterprise API.
**Differences:** Criteria-based (journalistic standards), not outcome-based (were they right?). Does not track individual predictions. Does not produce probability estimates. Easily gamed by outlets with good processes but bad calls.
**Threat level:** Low on methodology (fundamentally different). Medium on sales narrative — investors may conflate us.

---

### 10. Media Bias/Fact Check (MBFC)
**Category:** Media bias and factual accuracy ratings
**Description:** Human-curated database of 10,000+ sources rated for political bias and factual reporting. Free, donation-funded.
**Pricing:** Free.
**Similarities:** Media credibility scoring concept.
**Differences:** Manual, subjective, criteria-based. No API. No calibration. No individual prediction tracking.
**Threat level:** None (different tier entirely). Useful as a "before Bediavad" reference point.

---

### 11. Manifold Markets
**Category:** Social prediction market (play-money)
**Description:** Free play-money prediction platform. 2026 updates added Sharpe ratio, drawdown, and volatility scoring per user — moving toward calibration analytics.
**Pricing:** Free (play-money only).
**Similarities:** Per-user calibration tracking, open API, geopolitical questions.
**Differences:** Play-money, not real-money. No media/journalist tracking. No oracle API for institutional clients.
**Threat level:** Low.

---

### 12. Biasly
**Category:** Journalist bias and credibility scoring
**Description:** Hybrid AI + human analyst platform rating journalists and outlets on political bias and factual reliability. Individual journalist-level scoring.
**Pricing:** Not public; B2B/enterprise.
**Similarities:** Individual journalist-level credibility tracking, closest to our leaderboard concept.
**Differences:** Process/bias-based scoring, not outcome-based. No oracle API. No Hebrew/Israeli coverage.
**Threat level:** Low-medium on the leaderboard side.

---

### 13. Verso (Prediction Market Terminal)
**Category:** Prediction market analytics terminal
**Description:** Bloomberg-style terminal aggregating real-time Polymarket + Kalshi data for institutional traders. Analytics, news intelligence, market-implied probabilities.
**Pricing:** Not public; institutional.
**Similarities:** Serves the prediction market trader persona we target.
**Differences:** Consumes market prices (not independent calibration). No journalist scoring. No historical accuracy analysis.
**Threat level:** Low on product. Medium on buyer overlap.

---

### 14. PolyRadar / Polymarket Analytics Ecosystem
**Category:** Polymarket data layer
**Description:** Cluster of AI-powered analytics tools built on Polymarket data: PolyRadar (multi-model AI per event), Inside Edge (inefficiency detection), PolyMaster (whale tracking), Jatevo (6-agent AI research pipeline). 170+ tools in ecosystem, $2.5M+ in grants.
**Pricing:** Mostly free/freemium; some professional tiers.
**Similarities:** Intelligence layer for prediction market traders.
**Differences:** Anchored to Polymarket prices. No journalist scoring. No independent calibration.
**Threat level:** Low on methodology. Medium on buyer overlap.

---

### 15. Fact-Checkers (Snopes, PolitiFact, AFP Fact Check)
**Category:** Fact-checking
**Description:** Platforms that verify specific factual claims (usually after-the-fact) against sources. Human editorial process.
**Pricing:** Free (editorial-funded).
**Similarities to Bediavad (important to address explicitly):** Both deal with "what did media say vs. what is true."
**Key differences:**
- Fact-checkers verify **factual claims** ("Did X happen?"). We score **predictive claims** ("Will X happen?").
- Fact-checkers work claim-by-claim, manually. We work at scale with LLMs across thousands of articles.
- Fact-checkers have no calibration model, no journalist ranking, no oracle API.
- Fact-checkers are reactive and editorial. We are systematic and quantitative.
- Fact-checkers score the claim. We score the **forecaster**.
**Threat level:** None (different product). High risk of **perception confusion** — must be addressed in pitch.

---

## Competitive Positioning Summary

```
                    HIGH oracle accuracy
                           |
              Good Judgment |
                Metaculus   |
                            |
LOW media ──────────────────┼────────────────── HIGH media
scoring                     |                   scoring
                            |        [BEDIAVAD]
                            |
                    LOW oracle accuracy
                      (qualitative)
                           |
              Eurasia Group | Oxford Analytica
                  Stratfor  | NewsGuard
```

Bediavad occupies the empty top-right quadrant: high media scoring + high oracle accuracy.

---

## How to Handle the Fact-Checker Objection

In any investor pitch, address this proactively:

> *"We are often compared to fact-checkers like PolitiFact. The difference is fundamental: fact-checkers verify what happened. We measure who predicted it correctly — before it happened. That is a different problem, a different dataset, and a different product."*

---

## How to Handle the "Good Judgment is Better" Objection

> *"Good Judgment uses a curated panel of 180 human superforecasters. We use the actual track record of 25 major media sources over five years. Our data is larger, more systematic, and tied to the sources that institutional decision-makers already read. We are not replacing human judgment — we are scoring the sources they already use."*
