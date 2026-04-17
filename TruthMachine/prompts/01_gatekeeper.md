# Prompt: Stage 1 — Gatekeeper (Topic Relevance)

**Model:** Nova Micro (or equivalent ultra-low-cost model)
**Purpose:** Decide whether an article is relevant evidence for the related event.
**Output:** `GatekeeperOutput` structured via instructor.

**The live prompt is defined in `pipeline/src/tm/gatekeeper.py` (module constant `PROMPT`).**
This document describes intent; always consult the source for the exact text.

---

## Intent

The gatekeeper is a cheap topic-relevance filter. Its single job is to decide whether
an article contains useful evidence about the related event, so the expensive extractor
runs only on on-topic content.

It does **not** require explicit "X will happen" language. Purely factual articles
about the subject pass, because the downstream extractor derives stance from facts
and assigns its own certainty (low certainty ⇒ low weight in aggregation).

## Pass criteria

- Article discusses the related event directly (reports, announcements, statements).
- Article covers the specific actors, institutions, places, or situation underlying
  the event.
- Article reports causes, consequences, or recent developments a reasonable reader
  considers evidence for whether the event will occur.
- Article is explicit analysis, commentary, or speculation about the event.

## Reject criteria

- Wholly different event/domain (topical mismatch).
- Empty, paywall/404 stub, or no substantive content.
- Event keyword mentioned in passing while substance is unrelated.

## Schema

```python
class GatekeeperOutput(BaseModel):
    is_prediction: bool            # kept for backwards-compat; now means "is_useful_evidence"
    reason: str                    # one-sentence justification
    prediction_count_estimate: int # how many predictive signals a reader could extract
```

## Notes

- If `is_prediction` is false, the article is discarded and never sent to Stage 2 (extractor).
- `prediction_count_estimate` is purely informational; all aggregation weighting is done
  by the extractor's per-prediction certainty.
- Prompt operates on ~2500 chars of article text (`article_text[200:2700]`).
- If you change the prompt, update the intent section above — the source is always
  the single source of truth.
