# This project was developed with assistance from AI tools.
"""Tests for model config loading and validation."""

import textwrap
from pathlib import Path

import pytest

from src.inference import config as config_mod
from src.inference.config import _resolve_env_vars, load_config


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
          default_tier: llm
        models:
          llm:
            provider: openai_compatible
            model_name: test-model
            endpoint: http://localhost:8000/v1
          vision:
            provider: openai_compatible
            model_name: test-vision
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
          default_tier: llm
        models:
          llm:
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
          default_tier: llm
        models:
          llm:
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
          default_tier: llm
        models:
          llm:
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
          llm:
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


# -- Hot-reload --


def test_hot_reload_picks_up_mtime_change(tmp_path):
    """Config is reloaded when file mtime changes."""
    from src.inference.config import get_config

    _write_standard_config(tmp_path)
    cfg1 = get_config()
    assert cfg1["models"]["llm"]["model_name"] == "test-model"

    # Rewrite with a different model name
    import time

    time.sleep(0.05)  # ensure mtime differs
    cfg_path = config_mod._CONFIG_PATH
    cfg_path.write_text(
        textwrap.dedent("""\
        routing:
          default_tier: llm
        models:
          llm:
            provider: openai_compatible
            model_name: updated-model
            endpoint: http://localhost:8000/v1
        """)
    )

    cfg2 = get_config()
    assert cfg2["models"]["llm"]["model_name"] == "updated-model"


def test_hot_reload_keeps_cached_on_bad_yaml(tmp_path):
    """Broken YAML during hot-reload falls back to last valid config."""
    from src.inference.config import get_config

    _write_standard_config(tmp_path)
    cfg1 = get_config()
    assert cfg1["models"]["llm"]["model_name"] == "test-model"

    # Overwrite with invalid YAML
    import time

    time.sleep(0.05)
    config_mod._CONFIG_PATH.write_text("models: {bad yaml: [unterminated")

    cfg2 = get_config()
    # Should still return the old valid config
    assert cfg2["models"]["llm"]["model_name"] == "test-model"


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
          default_tier: llm
        models:
          llm:
            provider: openai_compatible
            model_name: recovered-model
            endpoint: http://localhost:8000/v1
        """)
    )

    cfg = get_config()
    assert cfg["models"]["llm"]["model_name"] == "recovered-model"


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
