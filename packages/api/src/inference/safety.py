# This project was developed with assistance from AI tools.
"""Safety shields via NeMo Guardrails.

Calls a NeMo Guardrails server through its /v1/guardrail/checks API to run
configured rails (regex patterns, PII detection, content safety NIM) against
user inputs and agent outputs.  This endpoint runs ONLY the rails -- it does
not trigger a full LLM inference, keeping check latency under ~5s.

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

    Uses NeMo's /v1/guardrail/checks endpoint to run configured rails (regex
    patterns, PII detection, content safety NIM) WITHOUT triggering a full
    LLM inference.  The previous /v1/chat/completions approach routed every
    check through the main LLM (~45s per call); /v1/guardrail/checks runs only
    the rails and returns in <5s.
    """

    def __init__(self, *, endpoint: str) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _call_nemo(self, messages: list[dict[str, str]]) -> SafetyResult:
        try:
            response = await self._client.post(
                f"{self._endpoint}/v1/guardrail/checks",
                json={
                    "model": "nemo-guardrails",
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "blocked":
                activated = (
                    data.get("guardrails_data", {}).get("log", {}).get("activated_rails", [])
                )
                rail_names = ", ".join(activated) if activated else "unknown"
                return SafetyResult(
                    is_safe=False,
                    violation_categories=activated or ["nemo_blocked"],
                    explanation=f"NeMo Guardrails blocked (rails: {rail_names})",
                )
            return SafetyResult(is_safe=True)

        except Exception:
            logger.error("NeMo Guardrails check failed, blocking (fail-closed)", exc_info=True)
            return SafetyResult(is_safe=False, explanation="Safety check unavailable")

    async def check_input(self, user_message: str) -> SafetyResult:
        """Check a user message for unsafe content via NeMo Guardrails."""
        return await self._call_nemo([{"role": "user", "content": user_message}])

    async def check_output(self, user_message: str, assistant_response: str) -> SafetyResult:
        """Check an assistant response for unsafe content via NeMo Guardrails."""
        return await self._call_nemo(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_response},
            ]
        )


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
