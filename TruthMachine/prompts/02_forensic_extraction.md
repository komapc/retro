# Prompt: Stage 2 — Forensic Extraction

**Model:** amazon.nova-lite-v1:0 (AWS Bedrock)
**Purpose:** Extract distinct forward-looking predictions from an article and quantify each one.
**Output:** JSON only
**max_tokens:** 1200

---

## Prompt

```
You are a forensic prediction analyst. Extract every distinct forward-looking prediction
from the article below and quantify each one.

Extract ALL predictions — not just explicit forecasts, but also:
- Implied directional views ("the economy is heading toward...")
- Vague sentiment that implies an outcome ("things are deteriorating")
- Predictions hidden between the lines in analysis or sourced commentary

STANCE DEFINITION — this is the most important field:
  stance measures how strongly the prediction implies the RELATED EVENT will occur.
  +1.0 = the author is certain the related event WILL happen
  -1.0 = the author is certain the related event WILL NOT happen
   0.0 = neutral / genuinely uncertain

  The related event is given below. Ask yourself: does this prediction imply the
  event is more likely (+) or less likely (-) to happen?

  Example: related event = "Assad regime falls in Syria"
    "Rebel forces are closing in on Hama" → stance +0.7  (implies Assad will fall)
    "Assad's army is holding the line"    → stance -0.6  (implies Assad will NOT fall)
    "The outcome remains uncertain"       → stance  0.0

  Do NOT use stance to indicate whether the outcome is good or bad.
  Use stance ONLY to indicate whether the prediction points toward the event happening.

For each prediction extract exactly four fields:
- quote: exact sentence(s) from the article (keep original language)
- claim: one-sentence neutral summary in English
- stance: float from -1.0 (event will NOT happen) to +1.0 (event WILL happen)
- certainty: float from 0.0 (very hedged) to 1.0 (absolute confidence)

Article:
<article>
{{ARTICLE_TEXT}}
</article>

Source: {{SOURCE_NAME}}
Journalist: {{JOURNALIST_NAME}} (or "unknown")
Date: {{ARTICLE_DATE}}
Related event: {{EVENT_NAME}} — {{EVENT_DESCRIPTION}}

Return up to 5 predictions. If more exist, take the most specific and highest-stance ones.
The claim field must be in English.

IMPORTANT: Your response must be a JSON object with a "predictions" key containing a list.
Example structure: {"predictions": [ {...}, {...} ]}
Do NOT return a bare JSON array. Always wrap in {"predictions": [...]}

CRITICAL: Each prediction must be a JSON object with exactly these four fields:
  quote (string), claim (string), stance (float -1 to 1), certainty (float 0-1)

Example — related event: "Assad regime falls in Syria":
{
  "quote": "Syrian rebel forces pushed close on Tuesday to the major city of Hama",
  "claim": "Rebel advances toward Hama make Assad's fall increasingly likely",
  "stance": 0.7,
  "certainty": 0.6
}
```

---

## Fields

| Field | Type | Description |
|---|---|---|
| `quote` | string | Exact sentence(s) from the article (original language) |
| `claim` | string | One-sentence English summary of the prediction |
| `stance` | float −1 to +1 | How strongly the prediction implies the event will occur |
| `certainty` | float 0–1 | Linguistic confidence: 0 = heavily hedged, 1 = absolute |

## Notes
- Extract **every** distinct prediction, even vague ones. Vague predictions receive low `certainty`.
- Do not translate the `quote` field — keep it in the original language.
- The `claim` field must be in English regardless of article language.
- Maximum predictions per article: 5. If more exist, take the most specific ones.
- `stance` is directional relative to the **related event** — not a general sentiment measure.

## Backward compatibility

Older atlas entries (pre-PR #102) contain nine additional fields per prediction:
`sentiment`, `specificity`, `hedge_ratio`, `conditionality`, `magnitude`,
`time_horizon`, `time_horizon_days`, `prediction_type`, `source_authority`.
These are retained as `Optional` in `PredictionExtraction` with `None` defaults
and are no longer requested from the LLM.
