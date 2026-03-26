import instructor
import litellm
from .models import ExtractionOutput
from .config import settings

litellm.api_key = settings.openrouter_api_key
_client = instructor.from_litellm(litellm.acompletion, mode=instructor.Mode.TOOLS)

PROMPT = """\
You are a forensic prediction analyst. Extract every distinct forward-looking prediction \
from the article below and quantify each one as structured metrics.

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

For each prediction:
- quote: exact sentence(s) from the article
- claim: one-sentence neutral summary in English (even if article is in Hebrew)
- stance: -1.0 (event will NOT happen) to +1.0 (event WILL happen)
- sentiment: 0.0 (cold/analytical) to 1.0 (highly charged/alarmed)
- certainty: 0.0 (very hedged) to 1.0 (absolute confidence)
- specificity: 0.0 (vague) to 1.0 (precise, named actors, dates, thresholds)
- hedge_ratio: 0.0 (no hedging) to 1.0 (entirely hedged with might/could/possibly)
- conditionality: 0.0 (unconditional) to 1.0 (fully conditional "only if X then Y")
- magnitude: 0.0 (minor/incremental) to 1.0 (historic/catastrophic)
- time_horizon: "days" / "weeks" / "months" / "years" / "unspecified"
- time_horizon_days: best estimate in days, null if unspecified
- prediction_type: "binary" / "continuous" / "range" / "trend"
- source_authority: 0.0 (personal opinion) to 1.0 (named insider/primary sources)

Article:
<article>
{article_text}
</article>

Source: {source_name}
Journalist: {journalist}
Date: {article_date}
Related event: {event_name} — {event_description}

Return up to 10 predictions. If more exist, take the most specific ones.
Do not translate the quote field — keep it in the original language.
The claim field must be in English.

CRITICAL: Each prediction must be a complete JSON object with ALL of these fields:
  quote (string), claim (string), stance (float -1 to 1), sentiment (float 0-1),
  certainty (float 0-1), specificity (float 0-1), hedge_ratio (float 0-1),
  conditionality (float 0-1), magnitude (float 0-1),
  time_horizon (one of: "days"/"weeks"/"months"/"years"/"unspecified"),
  time_horizon_days (integer or null), prediction_type (one of: "binary"/"continuous"/"range"/"trend"),
  source_authority (float 0-1)

Example — related event: "Assad regime falls in Syria":
{{
  "quote": "Syrian rebel forces pushed close on Tuesday to the major city of Hama",
  "claim": "Rebel advances toward Hama make Assad's fall increasingly likely",
  "stance": 0.7,
  "sentiment": 0.6,
  "certainty": 0.6,
  "specificity": 0.7,
  "hedge_ratio": 0.2,
  "conditionality": 0.1,
  "magnitude": 0.9,
  "time_horizon": "weeks",
  "time_horizon_days": 14,
  "prediction_type": "binary",
  "source_authority": 0.6
}}
"""


async def extract_predictions(
    article_text: str,
    source_name: str,
    article_date: str,
    event_name: str,
    event_description: str,
    journalist: str = "unknown",
) -> ExtractionOutput:
    return await _client.chat.completions.create(
        model=settings.extractor_model,
        response_model=ExtractionOutput,
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(
                    article_text=article_text,
                    source_name=source_name,
                    journalist=journalist,
                    article_date=article_date,
                    event_name=event_name,
                    event_description=event_description,
                ),
            }
        ],
        max_tokens=6000,
        timeout=45,
    )
