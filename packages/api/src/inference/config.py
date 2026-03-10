# This project was developed with assistance from AI tools.
"""Model routing configuration loader.

Reads config/models.yaml, substitutes ${ENV_VAR:-default} placeholders,
validates required fields, and supports mtime-based hot-reload so config
changes take effect without restarting the server.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Load .env into os.environ so YAML ${VAR} placeholders resolve correctly.
# pydantic-settings reads .env into its Settings object but doesn't set
# os.environ; the YAML config loader needs actual env vars.
load_dotenv()

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "models.yaml"
_cached_config: dict[str, Any] | None = None
_cached_mtime: float = 0.0

_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)(?::-(.*?))?\}")

REQUIRED_MODEL_FIELDS = {"provider", "model_name"}
# Remote providers also need an endpoint
_REMOTE_PROVIDERS = {"openai_compatible"}


def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR:-default} patterns with environment values.

    Follows bash ``:-`` semantics: the default is used when the variable
    is **unset or empty**.  This matters when Helm/k8s injects env vars
    with empty-string values for optional config.
    """

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2) or ""
        return os.environ.get(var_name) or default

    return _ENV_VAR_PATTERN.sub(_replace, value)


def _resolve_env_vars(obj: Any) -> Any:
    """Recursively resolve env var placeholders in a config tree."""
    if isinstance(obj, str):
        return _substitute_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def _validate_config(config: dict[str, Any]) -> None:
    """Validate that all required fields are present in each model definition."""
    models = config.get("models")
    if not models or not isinstance(models, dict):
        raise ValueError("models.yaml must contain a 'models' section with at least one model")

    routing = config.get("routing")
    if not routing or not isinstance(routing, dict):
        raise ValueError("models.yaml must contain a 'routing' section")

    default_tier = routing.get("default_tier")
    if default_tier and default_tier not in models:
        raise ValueError(
            f"routing.default_tier '{default_tier}' does not match any model in 'models'"
        )

    for name, model in models.items():
        if not isinstance(model, dict):
            raise ValueError(f"Model '{name}' must be a mapping")
        missing = REQUIRED_MODEL_FIELDS - set(model.keys())
        if missing:
            raise ValueError(f"Model '{name}' is missing required fields: {missing}")
        # Remote providers also require an endpoint
        provider = model.get("provider", "openai_compatible")
        if provider in _REMOTE_PROVIDERS and "endpoint" not in model:
            raise ValueError(f"Model '{name}' with provider '{provider}' requires 'endpoint'")


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load and validate models.yaml from disk."""
    config_path = path or _CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Model config not found: {config_path}")

    raw = config_path.read_text()
    config = yaml.safe_load(raw)
    config = _resolve_env_vars(config)
    _validate_config(config)
    return config


def get_config(path: Path | None = None) -> dict[str, Any]:
    """Return cached config, reloading if the file's mtime has changed."""
    global _cached_config, _cached_mtime  # noqa: PLW0603
    config_path = path or _CONFIG_PATH

    try:
        current_mtime = config_path.stat().st_mtime
    except FileNotFoundError:
        if _cached_config is not None:
            logger.warning("Config file disappeared, using cached config")
            return _cached_config
        raise

    if _cached_config is None or current_mtime > _cached_mtime:
        logger.info("Loading model config from %s", config_path)
        try:
            _cached_config = load_config(config_path)
            _cached_mtime = current_mtime

            # Invalidate cached HTTP clients so they pick up new endpoints/keys
            from .client import clear_client_cache

            clear_client_cache()

            # Reset the embedding provider so it picks up new config
            from .embeddings import reset_embedding_provider

            reset_embedding_provider()
        except (yaml.YAMLError, ValueError) as exc:
            if _cached_config is not None:
                logger.warning("Failed to reload config (%s), keeping last valid config", exc)
                _cached_mtime = current_mtime  # avoid retrying every call
            else:
                raise

    return _cached_config


def get_model_config(tier: str, path: Path | None = None) -> dict[str, Any]:
    """Return config for a specific model tier (e.g. 'fast_small', 'capable_large')."""
    config = get_config(path)
    models = config["models"]
    if tier not in models:
        raise KeyError(f"Unknown model tier '{tier}'. Available: {list(models.keys())}")
    return models[tier]


def get_model_tiers(path: Path | None = None) -> list[str]:
    """Return the names of all configured model tiers."""
    return list(get_config(path)["models"].keys())


def get_routing_config(path: Path | None = None) -> dict[str, Any]:
    """Return the routing section of config."""
    return get_config(path)["routing"]
