# This project was developed with assistance from AI tools.
"""Agent registry -- loads agent configs and returns configured graphs.

Each agent is defined by a YAML file in config/agents/ and backed by
a Python module in this package that builds the LangGraph graph.

Graphs are rebuilt when their YAML config file changes (mtime-based).
If a reload fails (bad YAML), the last valid graph is kept and a
warning is logged.
"""

import logging
import time
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_AGENTS_CONFIG_DIR = Path(__file__).resolve().parents[4] / "config" / "agents"

# Lazy-loaded agent graph cache: name -> (graph, mtime)
_graphs: dict[str, tuple[Any, float]] = {}

# Minimum interval (seconds) between filesystem stat() checks per agent.
_MTIME_CHECK_INTERVAL = 5.0
_last_check: dict[str, float] = {}


def load_agent_config(agent_name: str) -> dict[str, Any]:
    """Load a single agent's YAML config."""
    config_path = _AGENTS_CONFIG_DIR / f"{agent_name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Agent config not found: {config_path}")
    return yaml.safe_load(config_path.read_text())


# Agent module registry: agent name -> module path for lazy import
_AGENT_MODULES: dict[str, str] = {
    "public-assistant": ".public_assistant",
    "borrower-assistant": ".borrower_assistant",
    "loan-officer-assistant": ".loan_officer_assistant",
    "underwriter-assistant": ".underwriter_assistant",
    "ceo-assistant": ".ceo_assistant",
}


def _build_graph(agent_name: str, config: dict[str, Any], checkpointer=None):
    """Build a LangGraph graph for the named agent."""
    module_path = _AGENT_MODULES.get(agent_name)
    if module_path is None:
        raise ValueError(
            f"Unknown agent: {agent_name}. Registered agents: {sorted(_AGENT_MODULES.keys())}"
        )
    import importlib

    module = importlib.import_module(module_path, package=__package__)
    return module.build_graph(config, checkpointer=checkpointer)


def get_agent(agent_name: str, checkpointer=None):
    """Return a compiled LangGraph graph for the named agent.

    Graphs are cached and rebuilt when the config file's mtime changes.
    If a reload fails, the last valid graph is returned with a warning.
    """
    config_path = _AGENTS_CONFIG_DIR / f"{agent_name}.yaml"

    # Skip filesystem stat() if we checked recently
    now = time.monotonic()
    if agent_name in _graphs and now - _last_check.get(agent_name, 0) < _MTIME_CHECK_INTERVAL:
        return _graphs[agent_name][0]
    _last_check[agent_name] = now

    try:
        current_mtime = config_path.stat().st_mtime
    except FileNotFoundError:
        if agent_name in _graphs:
            logger.warning("Agent config disappeared for %s, using cached graph", agent_name)
            return _graphs[agent_name][0]
        raise

    if agent_name in _graphs:
        cached_graph, cached_mtime = _graphs[agent_name]
        if current_mtime <= cached_mtime:
            return cached_graph

    # Build or rebuild
    try:
        config = load_agent_config(agent_name)
        graph = _build_graph(agent_name, config, checkpointer=checkpointer)
        _graphs[agent_name] = (graph, current_mtime)
        logger.info("Loaded agent config for %s", agent_name)
        return graph
    except (yaml.YAMLError, ValueError, KeyError) as exc:
        if agent_name in _graphs:
            logger.warning(
                "Failed to reload agent config for %s (%s), keeping last valid graph",
                agent_name,
                exc,
            )
            # Update mtime to avoid retrying every call
            _graphs[agent_name] = (_graphs[agent_name][0], current_mtime)
            return _graphs[agent_name][0]
        raise


def clear_agent_cache() -> None:
    """Clear all cached agent graphs (useful for testing)."""
    _graphs.clear()
    _last_check.clear()


def list_agents() -> list[str]:
    """Return names of all available agents (based on YAML files on disk)."""
    if not _AGENTS_CONFIG_DIR.exists():
        return []
    return [p.stem for p in _AGENTS_CONFIG_DIR.glob("*.yaml")]
