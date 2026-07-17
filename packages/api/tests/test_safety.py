# This project was developed with assistance from AI tools.
"""Tests for NeMo Guardrails safety shields."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.core.config import settings
from src.inference.safety import NeMoGuardrailsChecker, get_safety_checker


@pytest.fixture(autouse=True)
def _disable_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DISABLED", True)


@pytest.fixture(autouse=True)
def _clear_checker_cache():
    """Reset the module-level checker cache between tests."""
    import src.inference.safety as safety_mod

    safety_mod._checker_instance = None
    yield
    safety_mod._checker_instance = None


@pytest.fixture
def checker():
    return NeMoGuardrailsChecker(endpoint="http://localhost:8080")


def _nemo_response(content: str) -> httpx.Response:
    """Build a fake NeMo Guardrails chat/completions response."""
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
        request=httpx.Request("POST", "http://localhost:8080/v1/chat/completions"),
    )


@pytest.mark.asyncio
async def test_check_input_safe(checker):
    """should return is_safe=True when NeMo passes the message through."""
    with patch.object(checker, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=_nemo_response("Your mortgage options are..."))
        result = await checker.check_input("What rates do you offer?")

    assert result.is_safe is True


@pytest.mark.asyncio
async def test_check_input_blocked(checker):
    """should return is_safe=False when NeMo returns a refusal."""
    with patch.object(checker, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=_nemo_response("I can't help with that"))
        result = await checker.check_input("something bad")

    assert result.is_safe is False
    assert "nemo_blocked" in result.violation_categories


@pytest.mark.asyncio
async def test_check_fails_closed_on_error(checker):
    """should return is_safe=False when the NeMo server is unreachable (fail-closed)."""
    with patch.object(checker, "_client") as mock_client:
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
        result = await checker.check_input("anything")

    assert result.is_safe is False
    assert result.explanation == "Safety check unavailable"


@pytest.mark.asyncio
async def test_check_output_calls_nemo(checker):
    """should send the assistant response to NeMo for output checking."""
    with patch.object(checker, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=_nemo_response("Looks good"))
        result = await checker.check_output("question", "We offer 30-year fixed at 6.5%.")

    assert result.is_safe is True
    mock_client.post.assert_called_once()


def test_get_safety_checker_returns_none_when_not_configured(monkeypatch):
    """should return None when NEMO_GUARDRAILS_ENDPOINT is not set."""
    monkeypatch.setattr(settings, "NEMO_GUARDRAILS_ENDPOINT", None)
    assert get_safety_checker() is None


def test_get_safety_checker_returns_instance_when_configured(monkeypatch):
    """should return a NeMoGuardrailsChecker when endpoint is set."""
    monkeypatch.setattr(settings, "NEMO_GUARDRAILS_ENDPOINT", "http://nemo:8080")
    checker = get_safety_checker()
    assert isinstance(checker, NeMoGuardrailsChecker)


def test_get_safety_checker_caches_instance(monkeypatch):
    """should return the same instance on subsequent calls."""
    monkeypatch.setattr(settings, "NEMO_GUARDRAILS_ENDPOINT", "http://nemo:8080")
    assert get_safety_checker() is get_safety_checker()
