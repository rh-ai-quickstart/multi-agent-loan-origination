# This project was developed with assistance from AI tools.
"""Safety shields via Llama Guard.

Calls Llama Guard 3 (8B) through the OpenAI-compatible API to check user
inputs and agent outputs against 13 safety categories (S1-S13).  The same
ChatOpenAI infrastructure used for inference models is reused here.

Design principle: shields ON by default when SAFETY_MODEL is set, degrade
gracefully (no-op + warning) when not configured.  Both input and output
checks fail-closed (block on error) -- in a regulated lending domain, the
risk of delivering an unverified response outweighs transient availability.
"""

import logging
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Full Llama Guard 3 category set (reference only -- not used directly).
LLAMA_GUARD_ALL_CATEGORIES = """\
S1: Violent Crimes
S2: Non-Violent Crimes
S3: Sex-Related Crimes
S4: Child Sexual Exploitation
S5: Defamation
S6: Specialized Advice
S7: Privacy
S8: Intellectual Property
S9: Indiscriminate Weapons
S10: Hate
S11: Suicide & Self-Harm
S12: Sexual Content
S13: Elections"""

# Domain-tuned categories for a mortgage intake application.
# S6 (Specialized Advice) and S7 (Privacy) are excluded from BOTH input and
# output checks because they conflict with the application's core purpose:
#
# S7 -- Privacy:
#   Input:  Users voluntarily provide PII (name, SSN, income) during intake.
#   Output: The agent must ask for PII to complete the application. Data-scope
#           filtering prevents cross-user PII leaks at the DB layer.
#
# S6 -- Specialized Advice:
#   Input:  Users asking for mortgage advice is the application's purpose.
#   Output: The agent provides mortgage guidance (rates, products, affordability)
#           as its primary function. Disclaimers are handled in the system prompt.
#
# S2 -- Non-Violent Crimes:
#   Input:  Underwriting decisions (approve/deny/suspend), adverse action notices,
#           debt-to-income analysis, and credit score discussions are core business
#           operations. Llama Guard consistently flags these as S2 despite added
#           context clarifying they are legitimate mortgage lending activities.
#   Output: The agent must communicate denial reasons, financial risk assessments,
#           and regulatory compliance details as part of its primary function.
LLAMA_GUARD_CATEGORIES = """\
S1: Violent Crimes
S3: Sex-Related Crimes
S4: Child Sexual Exploitation
S5: Defamation
S8: Intellectual Property
S9: Indiscriminate Weapons
S10: Hate
S11: Suicide & Self-Harm
S12: Sexual Content
S13: Elections"""

INPUT_CHECK_TEMPLATE = """\
<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if there is unsafe content in 'User' messages in conversations \
according to our safety policy with the below categories.

<BEGIN UNSAFE CONTENT CATEGORIES>
{categories}
<END UNSAFE CONTENT CATEGORIES>

<BEGIN CONTEXT>
This is a mortgage lending application. Users discuss loan terms such as \
"15-year", "30-year", "15 year fixed", etc. References to years or numbers \
in this context refer to loan durations, not people or ages. Evaluate \
messages in this financial services context.
<END CONTEXT>

<BEGIN CONVERSATION>

User: {user_message}

<END CONVERSATION>

Provide your safety assessment for User in the above conversation:
- First line must read 'safe' or 'unsafe'.
- If unsafe, a second line must include a comma-separated list of violated \
categories.<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

OUTPUT_CHECK_TEMPLATE = """\
<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if there is unsafe content in 'Agent' messages in conversations \
according to our safety policy with the below categories.

<BEGIN UNSAFE CONTENT CATEGORIES>
{categories}
<END UNSAFE CONTENT CATEGORIES>

<BEGIN CONVERSATION>

User: {user_message}

Agent: {assistant_response}

<END CONVERSATION>

Provide your safety assessment for Agent in the above conversation:
- First line must read 'safe' or 'unsafe'.
- If unsafe, a second line must include a comma-separated list of violated \
categories.<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""


@dataclass
class SafetyResult:
    """Result of a Llama Guard safety check."""

    is_safe: bool
    violation_categories: list[str] = field(default_factory=list)
    explanation: str = ""


class SafetyChecker:
    """Thin wrapper around Llama Guard via OpenAI-compatible API."""

    def __init__(self, *, model: str, endpoint: str, api_key: str) -> None:
        self._llm = ChatOpenAI(
            model=model,
            base_url=endpoint,
            api_key=api_key,
            temperature=0.0,
            max_tokens=100,
        )

    @staticmethod
    def _parse_response(text: str) -> SafetyResult:
        """Parse Llama Guard response into a SafetyResult."""
        lines = text.strip().splitlines()
        if not lines:
            return SafetyResult(is_safe=True, explanation="Empty response, treating as safe")

        verdict = lines[0].strip().lower()
        if verdict == "safe":
            return SafetyResult(is_safe=True)

        categories: list[str] = []
        if len(lines) > 1:
            categories = [c.strip() for c in lines[1].split(",") if c.strip()]

        return SafetyResult(
            is_safe=False,
            violation_categories=categories,
            explanation=f"Violated categories: {', '.join(categories)}" if categories else "",
        )

    async def check_input(self, user_message: str) -> SafetyResult:
        """Check a user message for unsafe content."""
        prompt = INPUT_CHECK_TEMPLATE.format(
            categories=LLAMA_GUARD_CATEGORIES,
            user_message=user_message,
        )
        try:
            response = await self._llm.ainvoke(prompt)
            return self._parse_response(response.content)
        except Exception:
            logger.error("Safety input check failed, blocking input (fail-closed)", exc_info=True)
            return SafetyResult(is_safe=False, explanation="Safety check unavailable")

    async def check_output(self, user_message: str, assistant_response: str) -> SafetyResult:
        """Check an assistant response for unsafe content."""
        prompt = OUTPUT_CHECK_TEMPLATE.format(
            categories=LLAMA_GUARD_CATEGORIES,
            user_message=user_message,
            assistant_response=assistant_response,
        )
        try:
            response = await self._llm.ainvoke(prompt)
            return self._parse_response(response.content)
        except Exception:
            logger.error("Safety output check failed, blocking output (fail-closed)", exc_info=True)
            return SafetyResult(is_safe=False, explanation="Safety check unavailable")


_checker_instance: SafetyChecker | None = None


def get_safety_checker() -> SafetyChecker | None:
    """Return a cached SafetyChecker if SAFETY_MODEL is configured, else None."""
    global _checker_instance  # noqa: PLW0603

    from ..core.config import settings

    if not settings.SAFETY_MODEL:
        return None

    if _checker_instance is None:
        _checker_instance = SafetyChecker(
            model=settings.SAFETY_MODEL,
            endpoint=settings.SAFETY_ENDPOINT or settings.LLM_BASE_URL,
            api_key=settings.SAFETY_API_KEY or settings.LLM_API_KEY,
        )

    return _checker_instance


def log_safety_status() -> None:
    """Log whether safety shields are active or degraded. Call at startup."""
    from ..core.config import settings

    if settings.SAFETY_MODEL:
        endpoint = settings.SAFETY_ENDPOINT or settings.LLM_BASE_URL
        logger.warning(
            "Safety shields: ACTIVE (model=%s, endpoint=%s)",
            settings.SAFETY_MODEL,
            endpoint,
        )
    else:
        logger.warning("Safety shields: DEGRADED (SAFETY_MODEL not set, shields disabled)")
