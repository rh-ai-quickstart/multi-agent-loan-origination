# This project was developed with assistance from AI tools.
"""Safety shields via NeMo Guardrails.

Calls a NeMo Guardrails server through its OpenAI-compatible API to check
user inputs and agent outputs against configured rails (forbidden words,
PII detection, content safety).

Design principle: shields ON by default when NEMO_GUARDRAILS_ENDPOINT is set,
degrade gracefully (no-op + warning) when not configured.  Both input and
output checks fail-closed (block on error) -- in a regulated lending domain,
the risk of delivering an unverified response outweighs transient availability.
"""

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SafetyResult:
    """Result of a safety check."""

    is_safe: bool
    violation_categories: list[str] = field(default_factory=list)
    explanation: str = ""


class NeMoGuardrailsChecker:
    """Safety checker via NeMo Guardrails server.

    Sends messages to NeMo's /v1/chat/completions endpoint.  NeMo runs
    input rails (forbidden words, PII detection, content safety) and
    either blocks with a canned refusal or passes through to the LLM.
    Blocking is detected by matching the response against known refusal phrases.
    """

    _REFUSAL_PATTERNS = [
        "i can't help with that",
        "i cannot help with that",
        "i don't know the answer",
        "i'm sorry, i can't respond to that",
    ]

    def __init__(self, *, endpoint: str) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    def _is_refusal(self, content: str) -> bool:
        lower = content.lower()
        return any(pattern in lower for pattern in self._REFUSAL_PATTERNS)

    async def _call_nemo(self, message: str) -> SafetyResult:
        try:
            response = await self._client.post(
                f"{self._endpoint}/v1/chat/completions",
                json={
                    "model": "nemo-guardrails",
                    "messages": [{"role": "user", "content": message}],
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            if self._is_refusal(content):
                return SafetyResult(
                    is_safe=False,
                    violation_categories=["nemo_blocked"],
                    explanation=f"NeMo Guardrails blocked: {content}",
                )
            return SafetyResult(is_safe=True)

        except Exception:
            logger.error(
                "NeMo Guardrails check failed, blocking (fail-closed)", exc_info=True
            )
            return SafetyResult(is_safe=False, explanation="Safety check unavailable")

    async def check_input(self, user_message: str) -> SafetyResult:
        """Check a user message for unsafe content via NeMo Guardrails."""
        return await self._call_nemo(user_message)

    async def check_output(self, user_message: str, assistant_response: str) -> SafetyResult:
        """Check an assistant response for unsafe content via NeMo Guardrails."""
        return await self._call_nemo(assistant_response)


_checker_instance: NeMoGuardrailsChecker | None = None


def get_safety_checker() -> NeMoGuardrailsChecker | None:
    """Return a cached NeMoGuardrailsChecker if NEMO_GUARDRAILS_ENDPOINT is set, else None."""
    global _checker_instance  # noqa: PLW0603

    from ..core.config import settings

    if not settings.NEMO_GUARDRAILS_ENDPOINT:
        return None

    if _checker_instance is None:
        _checker_instance = NeMoGuardrailsChecker(
            endpoint=settings.NEMO_GUARDRAILS_ENDPOINT,
        )

    return _checker_instance


def log_safety_status() -> None:
    """Log whether safety shields are active or degraded. Call at startup."""
    from ..core.config import settings

    if settings.NEMO_GUARDRAILS_ENDPOINT:
        logger.warning(
            "Safety shields: ACTIVE (NeMo Guardrails, endpoint=%s)",
            settings.NEMO_GUARDRAILS_ENDPOINT,
        )
    else:
        logger.warning(
            "Safety shields: DEGRADED (NEMO_GUARDRAILS_ENDPOINT not set, shields disabled)"
        )
