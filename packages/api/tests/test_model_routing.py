# This project was developed with assistance from AI tools.
"""Tests for model routing config loading and query classification."""

import textwrap
from pathlib import Path

import pytest

from src.inference import config as config_mod
from src.inference.config import _resolve_env_vars, load_config
from src.inference.router import classify_query


@pytest.fixture(autouse=True)
def _reset_config_cache():
    """Reset the config module cache before each test."""
    config_mod._cached_config = None
    config_mod._cached_mtime = 0.0
    original_path = config_mod._CONFIG_PATH
    yield
    config_mod._CONFIG_PATH = original_path
    config_mod._cached_config = None
    config_mod._cached_mtime = 0.0


def _write_standard_config(tmp_path: Path) -> None:
    """Write a standard test config and point the module at it."""
    cfg = tmp_path / "models.yaml"
    cfg.write_text(
        textwrap.dedent("""\
        routing:
          default_tier: capable_large
          classification:
            strategy: rule_based
            rules:
              simple:
                max_query_words: 10
                patterns: ["status", "when", "what is", "show me", "how much",
                           "hello", "hi", "thanks", "thank you"]
              complex:
                default: true
                keywords: ["compliance", "regulation", "dti", "debt-to-income",
                           "calculate", "affordability", "document", "underwriting",
                           "application", "ecoa", "trid", "hmda"]
        models:
          fast_small:
            provider: openai_compatible
            model_name: test-small
            endpoint: http://localhost:8000/v1
          capable_large:
            provider: openai_compatible
            model_name: test-large
            endpoint: http://localhost:8000/v1
        """)
    )
    config_mod._CONFIG_PATH = cfg


# -- Config validation --


def test_load_config_rejects_missing_model_fields(tmp_path):
    """Should reject a model missing required fields."""
    cfg = tmp_path / "models.yaml"
    cfg.write_text(
        textwrap.dedent("""\
        routing:
          default_tier: fast_small
        models:
          fast_small:
            provider: openai_compatible
        """)
    )
    with pytest.raises(ValueError, match="missing required fields"):
        load_config(cfg)


def test_load_config_rejects_remote_model_without_endpoint(tmp_path):
    """Should reject an openai_compatible model that has no endpoint."""
    cfg = tmp_path / "models.yaml"
    cfg.write_text(
        textwrap.dedent("""\
        routing:
          default_tier: fast_small
        models:
          fast_small:
            provider: openai_compatible
            model_name: test-model
        """)
    )
    with pytest.raises(ValueError, match="requires 'endpoint'"):
        load_config(cfg)


def test_load_config_accepts_local_model_without_endpoint(tmp_path):
    """Local provider models do not need an endpoint."""
    cfg = tmp_path / "models.yaml"
    cfg.write_text(
        textwrap.dedent("""\
        routing:
          default_tier: fast_small
        models:
          fast_small:
            provider: openai_compatible
            model_name: test-model
            endpoint: http://localhost:8000/v1
          embedding:
            provider: local
            model_name: nomic-ai/nomic-embed-text-v1.5
            dimensions: 768
        """)
    )
    config = load_config(cfg)
    assert config["models"]["embedding"]["provider"] == "local"
    assert "endpoint" not in config["models"]["embedding"]


def test_load_config_rejects_bad_default_tier(tmp_path):
    """Should reject default_tier pointing to nonexistent model."""
    cfg = tmp_path / "models.yaml"
    cfg.write_text(
        textwrap.dedent("""\
        routing:
          default_tier: nonexistent
        models:
          fast_small:
            provider: openai_compatible
            model_name: test
            endpoint: http://localhost:8000/v1
        """)
    )
    with pytest.raises(ValueError, match="does not match any model"):
        load_config(cfg)


def test_env_var_substitution(monkeypatch):
    """Should resolve ${VAR:-default} from environment."""
    monkeypatch.setenv("TEST_LLM_URL", "http://my-server:8080")
    result = _resolve_env_vars({"endpoint": "${TEST_LLM_URL:-http://fallback}"})
    assert result["endpoint"] == "http://my-server:8080"


def test_env_var_uses_default_when_unset():
    """Should use the default when env var is not set."""
    result = _resolve_env_vars({"endpoint": "${DEFINITELY_UNSET_VAR:-http://fallback}"})
    assert result["endpoint"] == "http://fallback"


def test_env_var_uses_default_when_empty(monkeypatch):
    """Should use the default when env var is set to empty string.

    Helm/k8s sets optional config to empty strings. The :- operator
    must treat empty the same as unset (matching bash semantics).
    """
    monkeypatch.setenv("EMPTY_TEST_VAR", "")
    result = _resolve_env_vars({"model": "${EMPTY_TEST_VAR:-fallback-model}"})
    assert result["model"] == "fallback-model"


# -- Query classification --


def test_classify_simple_pattern_routes_fast(tmp_path):
    """Short query matching a simple pattern should route to fast_small."""
    _write_standard_config(tmp_path)
    assert classify_query("What is my rate?") == "fast_small"


def test_classify_long_query_routes_complex(tmp_path):
    """Query exceeding max_query_words should route to capable_large."""
    _write_standard_config(tmp_path)
    result = classify_query(
        "I want to understand the full implications of refinancing my thirty year "
        "fixed rate mortgage into a fifteen year adjustable rate product"
    )
    assert result == "capable_large"


def test_classify_complex_keyword_routes_capable(tmp_path):
    """Query containing a complex keyword should route to capable_large."""
    _write_standard_config(tmp_path)
    assert classify_query("What are the DTI requirements?") == "capable_large"


def test_classify_complex_keyword_takes_precedence(tmp_path):
    """Complex keyword should override short-query heuristic."""
    _write_standard_config(tmp_path)
    # "DTI limit?" is short (2 words) but contains complex keyword "dti"
    assert classify_query("DTI limit?") == "capable_large"


# -- Hot-reload --


def test_hot_reload_picks_up_mtime_change(tmp_path):
    """Config is reloaded when file mtime changes."""
    from src.inference.config import get_config

    _write_standard_config(tmp_path)
    cfg1 = get_config()
    assert cfg1["models"]["fast_small"]["model_name"] == "test-small"

    # Rewrite with a different model name
    import time

    time.sleep(0.05)  # ensure mtime differs
    cfg_path = config_mod._CONFIG_PATH
    cfg_path.write_text(
        textwrap.dedent("""\
        routing:
          default_tier: capable_large
        models:
          fast_small:
            provider: openai_compatible
            model_name: updated-small
            endpoint: http://localhost:8000/v1
          capable_large:
            provider: openai_compatible
            model_name: test-large
            endpoint: http://localhost:8000/v1
        """)
    )

    cfg2 = get_config()
    assert cfg2["models"]["fast_small"]["model_name"] == "updated-small"


def test_hot_reload_keeps_cached_on_bad_yaml(tmp_path):
    """Broken YAML during hot-reload falls back to last valid config."""
    from src.inference.config import get_config

    _write_standard_config(tmp_path)
    cfg1 = get_config()
    assert cfg1["models"]["fast_small"]["model_name"] == "test-small"

    # Overwrite with invalid YAML
    import time

    time.sleep(0.05)
    config_mod._CONFIG_PATH.write_text("models: {bad yaml: [unterminated")

    cfg2 = get_config()
    # Should still return the old valid config
    assert cfg2["models"]["fast_small"]["model_name"] == "test-small"


def test_hot_reload_recovers_after_fix(tmp_path):
    """Corrected config is picked up after a bad reload."""
    from src.inference.config import get_config

    _write_standard_config(tmp_path)
    get_config()

    # Break it
    import time

    time.sleep(0.05)
    config_mod._CONFIG_PATH.write_text("not: valid: yaml: [")
    get_config()  # falls back to cached

    # Fix it
    time.sleep(0.05)
    config_mod._CONFIG_PATH.write_text(
        textwrap.dedent("""\
        routing:
          default_tier: capable_large
        models:
          fast_small:
            provider: openai_compatible
            model_name: recovered-small
            endpoint: http://localhost:8000/v1
          capable_large:
            provider: openai_compatible
            model_name: test-large
            endpoint: http://localhost:8000/v1
        """)
    )

    cfg = get_config()
    assert cfg["models"]["fast_small"]["model_name"] == "recovered-small"


def test_startup_fails_on_missing_config():
    """Missing config at startup raises FileNotFoundError."""
    from src.inference.config import get_config

    config_mod._CONFIG_PATH = Path("/nonexistent/models.yaml")
    with pytest.raises(FileNotFoundError):
        get_config()


def test_startup_fails_on_invalid_config(tmp_path):
    """Invalid config at startup raises ValueError."""
    from src.inference.config import get_config

    cfg = tmp_path / "models.yaml"
    cfg.write_text("models: not_a_dict")
    config_mod._CONFIG_PATH = cfg
    with pytest.raises(ValueError, match="must contain a 'models' section"):
        get_config()
