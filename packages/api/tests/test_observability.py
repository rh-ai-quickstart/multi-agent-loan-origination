# This project was developed with assistance from AI tools.
"""Tests for MLFlow observability integration."""

from unittest.mock import patch

import pytest

from src.core.config import settings
from src.observability import (
    _configure_auth,
    _is_configured,
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


# -- _configure_auth tests --


def test_configure_auth_kubernetes_mode(monkeypatch, caplog):
    """should use Kubernetes auth plugin when MLFLOW_TRACKING_AUTH=kubernetes."""
    import logging

    monkeypatch.setattr(settings, "MLFLOW_TRACKING_TOKEN", None)
    monkeypatch.setattr(settings, "MLFLOW_WORKSPACE", None)
    monkeypatch.setenv("MLFLOW_TRACKING_AUTH", "kubernetes")

    with caplog.at_level(logging.INFO):
        _configure_auth()

    assert "Kubernetes plugin" in caplog.text
    monkeypatch.delenv("MLFLOW_TRACKING_AUTH", raising=False)


def test_configure_auth_kubernetes_auto_detects_namespace(monkeypatch, tmp_path, caplog):
    """should auto-detect workspace from pod namespace when MLFLOW_TRACKING_AUTH=kubernetes."""
    import logging
    import os

    import src.observability as obs

    ns_file = tmp_path / "namespace"
    ns_file.write_text("mortgage-ai")
    monkeypatch.setattr(obs, "_SA_NAMESPACE_PATH", ns_file)
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_TOKEN", None)
    monkeypatch.setattr(settings, "MLFLOW_WORKSPACE", None)
    monkeypatch.setenv("MLFLOW_TRACKING_AUTH", "kubernetes")

    with caplog.at_level(logging.INFO):
        _configure_auth()

    assert os.environ.get("MLFLOW_WORKSPACE") == "mortgage-ai"
    assert "auto-detected" in caplog.text
    monkeypatch.delenv("MLFLOW_TRACKING_AUTH", raising=False)
    monkeypatch.delenv("MLFLOW_WORKSPACE", raising=False)


def test_configure_auth_explicit_token(monkeypatch, caplog):
    """should use explicit MLFLOW_TRACKING_TOKEN when set."""
    import logging
    import os

    monkeypatch.setattr(settings, "MLFLOW_TRACKING_TOKEN", "my-explicit-token")
    monkeypatch.delenv("MLFLOW_TRACKING_AUTH", raising=False)

    with caplog.at_level(logging.INFO):
        _configure_auth()

    assert os.environ.get("MLFLOW_TRACKING_TOKEN") == "my-explicit-token"
    assert "explicit" in caplog.text
    monkeypatch.delenv("MLFLOW_TRACKING_TOKEN", raising=False)


def test_configure_auth_sa_token_fallback(monkeypatch, tmp_path, caplog):
    """should read mounted SA token as fallback when no other auth is set."""
    import logging
    import os

    import src.observability as obs

    token_file = tmp_path / "token"
    token_file.write_text("sa-token-value")
    monkeypatch.setattr(obs, "_SA_TOKEN_PATH", token_file)
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_TOKEN", None)
    monkeypatch.delenv("MLFLOW_TRACKING_AUTH", raising=False)

    with caplog.at_level(logging.INFO):
        _configure_auth()

    assert os.environ.get("MLFLOW_TRACKING_TOKEN") == "sa-token-value"
    assert "mounted ServiceAccount" in caplog.text
    monkeypatch.delenv("MLFLOW_TRACKING_TOKEN", raising=False)


def test_configure_auth_no_credentials(monkeypatch, tmp_path, caplog):
    """should warn when no auth credentials are found."""
    import logging

    import src.observability as obs

    monkeypatch.setattr(obs, "_SA_TOKEN_PATH", tmp_path / "nonexistent")
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_TOKEN", None)
    monkeypatch.delenv("MLFLOW_TRACKING_AUTH", raising=False)

    with caplog.at_level(logging.WARNING):
        _configure_auth()

    assert "no credentials" in caplog.text


def test_configure_auth_kubernetes_skips_namespace_when_workspace_set(monkeypatch, tmp_path):
    """should not override MLFLOW_WORKSPACE when explicitly set."""
    import os

    import src.observability as obs

    ns_file = tmp_path / "namespace"
    ns_file.write_text("auto-detected-ns")
    monkeypatch.setattr(obs, "_SA_NAMESPACE_PATH", ns_file)
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_TOKEN", None)
    monkeypatch.setattr(settings, "MLFLOW_WORKSPACE", "explicit-workspace")
    monkeypatch.setenv("MLFLOW_TRACKING_AUTH", "kubernetes")

    _configure_auth()

    # Should NOT be overridden by auto-detection
    assert os.environ.get("MLFLOW_WORKSPACE") != "auto-detected-ns"
    monkeypatch.delenv("MLFLOW_TRACKING_AUTH", raising=False)
    monkeypatch.delenv("MLFLOW_WORKSPACE", raising=False)


def test_init_tracing_uses_kubernetes_auth(monkeypatch, reset_autolog):
    """should use _configure_auth with kubernetes mode during init."""
    import os

    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_TOKEN", None)
    monkeypatch.setattr(settings, "MLFLOW_WORKSPACE", "test-ws")
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_INSECURE_TLS", False)
    monkeypatch.setenv("MLFLOW_TRACKING_AUTH", "kubernetes")

    with patch("threading.Thread"):
        init_mlflow_tracing()

    assert os.environ.get("MLFLOW_WORKSPACE") == "test-ws"
    monkeypatch.delenv("MLFLOW_TRACKING_AUTH", raising=False)
    monkeypatch.delenv("MLFLOW_WORKSPACE", raising=False)
