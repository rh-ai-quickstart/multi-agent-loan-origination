# This project was developed with assistance from AI tools.
"""Tests for MLFlow observability integration."""

from unittest.mock import patch

import pytest

from src.core.config import settings
from src.observability import (
    _is_configured,
    _read_sa_token,
    init_mlflow_tracing,
    log_observability_status,
    set_trace_context,
)


@pytest.fixture(autouse=True)
def _disable_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DISABLED", True)


@pytest.fixture
def reset_autolog():
    """Reset the _autolog_enabled flag before each test."""
    import src.observability as obs

    obs._autolog_enabled = False
    yield
    obs._autolog_enabled = False


def test_is_configured_returns_false_when_no_uri(monkeypatch):
    """should return False when MLFLOW_TRACKING_URI is not set."""
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", None)
    assert _is_configured() is False


def test_is_configured_returns_false_when_empty_uri(monkeypatch):
    """should return False when MLFLOW_TRACKING_URI is empty string."""
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "")
    assert _is_configured() is False


def test_is_configured_returns_true_when_uri_set(monkeypatch):
    """should return True when MLFLOW_TRACKING_URI is set."""
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://localhost:5000")
    assert _is_configured() is True


def test_init_tracing_noop_when_unconfigured(monkeypatch, reset_autolog):
    """should do nothing when MLFlow is not configured."""
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", None)

    init_mlflow_tracing()

    import src.observability as obs

    assert obs._autolog_enabled is False


@patch("mlflow.langchain.autolog")
@patch("mlflow.set_experiment")
@patch("mlflow.set_tracking_uri")
def test_init_tracing_when_configured(
    mock_set_uri, mock_set_exp, mock_autolog, monkeypatch, reset_autolog
):
    """should initialize MLFlow autolog when configured."""
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://localhost:5000")
    monkeypatch.setattr(settings, "MLFLOW_EXPERIMENT_NAME", "test-experiment")

    init_mlflow_tracing()

    mock_set_uri.assert_called_once_with("http://localhost:5000")
    mock_set_exp.assert_called_once_with("test-experiment")
    mock_autolog.assert_called_once_with()

    import src.observability as obs

    assert obs._autolog_enabled is True


@pytest.mark.skip(
    reason="Unmocked mlflow.set_experiment connects to localhost:5000, times out after ~4min"
)
@patch("mlflow.langchain.autolog")
def test_init_tracing_catches_errors(mock_autolog, monkeypatch, reset_autolog):
    """should catch and log errors during initialization."""
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://localhost:5000")
    mock_autolog.side_effect = RuntimeError("connection refused")

    # Should not raise
    init_mlflow_tracing()

    import src.observability as obs

    assert obs._autolog_enabled is False


def test_set_context_noop_when_unconfigured(monkeypatch, reset_autolog):
    """should do nothing when autolog is not enabled."""
    import src.observability as obs

    obs._autolog_enabled = False

    # Should not raise
    set_trace_context(session_id="test-session", user_id="test-user")


@patch("mlflow.set_tag")
def test_set_context_sets_tags_when_enabled(mock_set_tag, monkeypatch, reset_autolog):
    """should set MLFlow tags when autolog is enabled."""
    import src.observability as obs

    obs._autolog_enabled = True

    set_trace_context(session_id="sess-123", user_id="user-1", tags=["test", "demo"])

    mock_set_tag.assert_any_call("session_id", "sess-123")
    mock_set_tag.assert_any_call("user_id", "user-1")
    mock_set_tag.assert_any_call("tags", "test,demo")


@patch("mlflow.set_tag")
def test_set_context_omits_optional_fields(mock_set_tag, monkeypatch, reset_autolog):
    """should not set user_id or tags when not provided."""
    import src.observability as obs

    obs._autolog_enabled = True

    set_trace_context(session_id="sess-456")

    assert mock_set_tag.call_count == 1
    mock_set_tag.assert_called_once_with("session_id", "sess-456")


@patch("mlflow.set_tag")
def test_set_context_catches_errors(mock_set_tag, monkeypatch, reset_autolog):
    """should not raise when setting tags fails."""
    import src.observability as obs

    obs._autolog_enabled = True
    mock_set_tag.side_effect = RuntimeError("mlflow error")

    # Should not raise
    set_trace_context(session_id="sess-err")


def test_log_status_when_unconfigured(monkeypatch, caplog):
    """should log DISABLED status when MLFlow is not configured."""
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", None)

    import logging

    with caplog.at_level(logging.INFO):
        log_observability_status()

    assert "DISABLED" in caplog.text


def test_log_status_when_configured(monkeypatch, reset_autolog, caplog):
    """should log CONFIGURED status when MLFlow URI is set."""
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://localhost:5000")
    monkeypatch.setattr(settings, "MLFLOW_EXPERIMENT_NAME", "test-exp")

    import logging

    with caplog.at_level(logging.INFO):
        log_observability_status()

    assert "http://localhost:5000" in caplog.text
    assert "test-exp" in caplog.text


# -- _read_sa_token tests --


def test_read_sa_token_returns_token_when_file_exists(tmp_path, monkeypatch):
    """should return token content when SA token file exists."""
    import src.observability as obs

    token_file = tmp_path / "token"
    token_file.write_text("eyJhbGciOiJSUzI1NiIs...\n")
    monkeypatch.setattr(obs, "_SA_TOKEN_PATH", token_file)

    assert _read_sa_token() == "eyJhbGciOiJSUzI1NiIs..."


def test_read_sa_token_returns_none_when_file_missing(tmp_path, monkeypatch):
    """should return None when SA token file does not exist."""
    import src.observability as obs

    monkeypatch.setattr(obs, "_SA_TOKEN_PATH", tmp_path / "nonexistent")

    assert _read_sa_token() is None


def test_read_sa_token_returns_none_when_file_empty(tmp_path, monkeypatch):
    """should return None when SA token file is empty."""
    import src.observability as obs

    token_file = tmp_path / "token"
    token_file.write_text("")
    monkeypatch.setattr(obs, "_SA_TOKEN_PATH", token_file)

    assert _read_sa_token() is None


def test_init_tracing_uses_sa_token_when_no_explicit_token(monkeypatch, reset_autolog, tmp_path):
    """should use SA token when MLFLOW_TRACKING_TOKEN is not set."""
    import os

    import src.observability as obs

    token_file = tmp_path / "token"
    token_file.write_text("sa-token-value")
    monkeypatch.setattr(obs, "_SA_TOKEN_PATH", token_file)
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_TOKEN", None)
    monkeypatch.setattr(settings, "MLFLOW_WORKSPACE", None)
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_INSECURE_TLS", False)

    with patch("threading.Thread"):
        init_mlflow_tracing()

    assert os.environ.get("MLFLOW_TRACKING_TOKEN") == "sa-token-value"
    # Clean up
    monkeypatch.delenv("MLFLOW_TRACKING_TOKEN", raising=False)


def test_init_tracing_prefers_explicit_token_over_sa(monkeypatch, reset_autolog, tmp_path):
    """should prefer explicit MLFLOW_TRACKING_TOKEN over SA token."""
    import os

    import src.observability as obs

    token_file = tmp_path / "token"
    token_file.write_text("sa-token-value")
    monkeypatch.setattr(obs, "_SA_TOKEN_PATH", token_file)
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_TOKEN", "explicit-token")
    monkeypatch.setattr(settings, "MLFLOW_WORKSPACE", None)
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_INSECURE_TLS", False)

    with patch("threading.Thread"):
        init_mlflow_tracing()

    assert os.environ.get("MLFLOW_TRACKING_TOKEN") == "explicit-token"
    # Clean up
    monkeypatch.delenv("MLFLOW_TRACKING_TOKEN", raising=False)
