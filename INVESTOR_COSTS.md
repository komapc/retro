# TruthMachine / Factum Atlas — MVP Cost Estimate (6 months)

**Scope:** 100×200 Middle East matrix, 5+ years retro fill + Daatan Forecast Android app targeting 200k MAU.
**Assumptions:** Israel-based team, zero revenue, promotion excluded, AWS infrastructure.

---

## 1. Personnel

Three people: 2 founders (full market salary) + 1 mathematician / data engineer (new hire).

| Role | Gross salary (NIS/mo) | Duration | Total incl. employer costs (~28%) |
|---|---|---|---|
| Founder × 2 | 20,000 each = 40,000 | 6 months | ~₪307,000 (~$83,000) |
| Mathematician / data engineer | 20,000 | Months 4–6 only | ~₪77,000 (~$20,800) |
| **Total personnel** | | | **~$103,800** |

> Third hire joins Month 4 once retro fill is underway and TruthMachine design is ready to implement.
> Israeli employer costs include bituach leumi, pension (6.5%), advanced training fund (7.5%).
> Exchange rate assumed: ₪3.7 = $1.

---

## 2. Paid content access — archives, paywalls, licensing

~20 of 100 sources require paid access (Haaretz archive, Calcalist, Globes, key Arabic sources).
CDX/Wayback covers the remaining ~80% for historical content.

| Item | 6-month cost |
|---|---|
| Haaretz digital archive / API | $800–2,000 |
| Hebrew business press (Globes, Calcalist) | $600–1,500 |
| Arabic source archives (2–3 key outlets) | $500–1,500 |
| Contingency (paywall gaps in retro fill) | $1,000–3,000 |
| **Total** | **$3,000–8,000** |

---

## 3. Cloud infrastructure (AWS)

Currently <$100/mo. Scales with Daatan Forecast user growth.

| Phase | Monthly | Total |
|---|---|---|
| Months 1–3 (build + small user base) | ~$250–400 | ~$900 |
| Months 4–6 (scaling to 200k MAU) | ~$600–1,200 | ~$2,400 |
| **Total 6 months** | | **$3,000–5,500** |

> Includes EC2 (pipeline + API), RDS, S3, CloudFront, load balancer.
> At 200k MAU the app is read-heavy with pre-computed data — manageable on 2–3 mid-range instances.

---

## 4. LLM API cost (retro fill + ongoing)

Pipeline uses Gemini 2.0 Flash Lite via OpenRouter (~$0.075/1M input tokens).

| Item | Estimate |
|---|---|
| Retro fill: 20,000 cells × ~10 articles, gatekeeper + extractor passes | ~$200–400 one-time |
| Ongoing monthly (new events, rescoring) | ~$50–100/mo → ~$300 over 6 months |
| **Total** | **~$500–700** |

> This is the cheapest line item. Gemini Flash Lite makes LLM costs almost negligible at this scale.

---

## 5. Translation infrastructure (Google Translate API)

Arabic + Turkish for MVP. Extraction is done in English post-translation.

| Item | Estimate |
|---|---|
| Retro fill: ~30% of sources × 200k articles × ~5,000 chars | ~$4,000–7,000 one-time |
| Ongoing monthly | ~$200–400/mo → ~$1,200 over 6 months |
| **Total** | **$5,000–8,500** |

---

## 6. Legal / IP counsel + incorporation

Company not yet incorporated.

| Item | Cost |
|---|---|
| Israeli company incorporation (lawyer + gov fees) | $1,500–3,000 |
| App ToS, privacy policy, data processing agreements | $1,500–3,500 |
| Light ongoing counsel (scraping ToS review, licensing) | $500–1,000/mo → $2,000–4,000 |
| **Total** | **$5,000–10,500** |

---

## 7. Human QA / annotation

Journalism and domain expertise covered internally. Budget is for ML output spot-checks only.

| Item | Cost |
|---|---|
| Freelance spot-check annotators (Arabic, Turkish) | $1,000–2,000 |
| TruthMachine output validation (edge cases) | $500–1,500 |
| **Total** | **$1,500–3,500** |

---

## 8. Prediction market & financial data feeds

Polymarket currently scraped free. Minimal additional feeds needed for ME matrix.

| Item | Cost |
|---|---|
| Licensed / stable data feeds (contingency) | $500–2,000 |
| **Total** | **$500–2,000** |

---

## 9. Promotion / campaign

**Excluded from this estimate.** Viral growth assumed for Daatan Forecast.

---

## Consolidated 6-Month Budget

| Category | Low | High |
|---|---|---|
| Personnel (2 founders 6mo + 1 engineer months 4–6) | $103,800 | $103,800 |
| Paid content access | $3,000 | $8,000 |
| Cloud infrastructure (AWS) | $3,000 | $5,500 |
| Translation API | $5,000 | $8,500 |
| Legal / incorporation | $5,000 | $10,500 |
| LLM API (Gemini Flash Lite) | $500 | $700 |
| Human QA / annotation | $1,500 | $3,500 |
| Data feeds | $500 | $2,000 |
| **Total** | **$112,800** | **$128,800** |

**Working figure: ~$124,000 for 6 months — fits within YC $125k program.**

---

## Key observations for investors

1. **Personnel is 85–90% of total cost.** Everything else is noise by comparison.
2. **LLM costs are negligible** — Gemini Flash Lite at $0.075/1M tokens makes the pipeline economics extremely favorable.
3. **Translation is the #2 technical cost**, not LLM inference. Arabic/Turkish retro fill at scale costs more than all LLM calls combined.
4. **Content access risk is real** — 83% of current test cells return no predictions, partly due to paywall gaps in Wayback. Budget ~$3–8k to patch the worst offenders.
5. **Viral assumption is load-bearing** — if Daatan Forecast does not grow organically, the $0 promotion budget means the 200k MAU target is unachievable without additional spend.

---

*Promotion, revenue model, and valuation are addressed separately.*
