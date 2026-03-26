import instructor
import litellm
from .models import GatekeeperOutput
from .config import settings

litellm.api_key = settings.openrouter_api_key
_client = instructor.from_litellm(litellm.acompletion, mode=instructor.Mode.TOOLS)

PROMPT = """\
You are a forensic analyst screening news articles for predictive content.

Determine whether the following article snippet contains a **forward-looking prediction** — \
a claim about what will or may happen, or what the author believes will happen.

Include:
- Explicit predictions ("X will happen", "we expect Y")
- Strong directional forecasts ("the market is headed for collapse")
- Conditional predictions ("if X happens, then Y is likely")
- Implied forecasts based on analysis ("the signs point to Z")
- Vague sentiment that implies a directional view ("things are getting worse")

Exclude:
- Pure factual reporting of past or present events
- Historical context without forward implication
- Rhetorical questions without answers
- Pure opinion with no predictive content

Article snippet:
<article>
{article_text}
</article>

Source: {source_name}
Date: {article_date}
Related event: {event_name}
"""


async def check_is_prediction(
    article_text: str,
    source_name: str,
    article_date: str,
    event_name: str,
) -> GatekeeperOutput:
    return await _client.chat.completions.create(
        model=settings.gatekeeper_model,
        response_model=GatekeeperOutput,
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(
                    article_text=article_text[200:2700],
                    source_name=source_name,
                    article_date=article_date,
                    event_name=event_name,
                ),
            }
        ],
        max_tokens=200,
        timeout=20,
    )
