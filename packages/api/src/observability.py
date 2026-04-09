# This project was developed with assistance from AI tools.
"""MLFlow observability integration.

Provides automatic tracing for LangGraph/LangChain via MLFlow autolog.
When MLFLOW_TRACKING_URI is set, all LangChain operations are automatically
traced without requiring explicit callbacks.

Design principle (mirrors safety.py): tracing is active when MLFLOW_TRACKING_URI
is set, degrades gracefully (no-op + warning) when not configured, and never
blocks the conversation on a tracing error.

Authentication modes (in priority order):
  1. MLFLOW_TRACKING_AUTH=kubernetes -- Red Hat RHOAI 3.4+ Kubernetes plugin.
     Reads the mounted ServiceAccount token and namespace automatically.
     No manual token generation needed.
  2. MLFLOW_TRACKING_TOKEN -- explicit bearer token (manual or from secret).
  3. Mounted SA token at /run/secrets/kubernetes.io/serviceaccount/token --
     legacy fallback, reads the file directly.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Kubernetes ServiceAccount paths (auto-mounted by the kubelet)
_SA_TOKEN_PATH = Path("/run/secrets/kubernetes.io/serviceaccount/token")
_SA_NAMESPACE_PATH = Path("/run/secrets/kubernetes.io/serviceaccount/namespace")

_autolog_enabled = False


def _is_configured() -> bool:
    """Return True when MLFlow tracking URI is set."""
    from .core.config import settings

    return bool(settings.MLFLOW_TRACKING_URI)


def _configure_auth() -> None:
    """Configure MLflow authentication from available sources.

    Priority:
      1. MLFLOW_TRACKING_AUTH=kubernetes (RHOAI 3.4+ plugin) -- handles
         token and workspace automatically from the mounted ServiceAccount.
      2. Explicit MLFLOW_TRACKING_TOKEN env var / setting.
      3. Mounted ServiceAccount token file (legacy fallback).
    """
    from .core.config import settings

    # Mode 1: Kubernetes auth plugin (RHOAI 3.4+).
    # When set, the Red Hat MLflow fork reads the SA token and derives
    # the workspace from the pod namespace automatically.
    if os.environ.get("MLFLOW_TRACKING_AUTH") == "kubernetes":
        logger.info("MLflow auth: using Kubernetes plugin (MLFLOW_TRACKING_AUTH=kubernetes)")
        # Auto-detect workspace from pod namespace if not explicitly set
        if not settings.MLFLOW_WORKSPACE and _SA_NAMESPACE_PATH.is_file():
            try:
                namespace = _SA_NAMESPACE_PATH.read_text().strip()
                if namespace:
                    os.environ["MLFLOW_WORKSPACE"] = namespace
                    logger.info("MLflow workspace auto-detected from pod namespace: %s", namespace)
            except OSError:
                logger.debug("Could not read namespace from %s", _SA_NAMESPACE_PATH)
        return

    # Mode 2: Explicit token from settings or env var.
    if settings.MLFLOW_TRACKING_TOKEN:
        os.environ["MLFLOW_TRACKING_TOKEN"] = settings.MLFLOW_TRACKING_TOKEN
        logger.info("MLflow auth: using explicit MLFLOW_TRACKING_TOKEN")
        return

    # Mode 3: Read mounted ServiceAccount token directly (legacy).
    try:
        if _SA_TOKEN_PATH.is_file():
            token = _SA_TOKEN_PATH.read_text().strip()
            if token:
                os.environ["MLFLOW_TRACKING_TOKEN"] = token
                logger.info(
                    "MLflow auth: using mounted ServiceAccount token from %s", _SA_TOKEN_PATH
                )
                return
    except OSError:
        logger.debug("Could not read SA token at %s", _SA_TOKEN_PATH, exc_info=True)

    logger.warning("MLflow auth: no credentials found -- requests may fail")


def _do_mlflow_init() -> None:
    """Perform the actual MLflow initialization (may block on HTTP calls)."""
    global _autolog_enabled

    try:
        import mlflow
        import mlflow.langchain

        from .core.config import settings

        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)
        mlflow.langchain.autolog()
        _autolog_enabled = True
        logger.info("MLFlow autolog initialized successfully")
    except Exception:
        logger.warning("Failed to initialize MLFlow tracing", exc_info=True)


def init_mlflow_tracing() -> None:
    """Initialize MLFlow autolog for LangChain/LangGraph tracing.

    Call once at application startup. When MLFLOW_TRACKING_URI is configured,
    this enables automatic tracing of all LangChain operations via autolog.

    Runs in a background thread to avoid blocking app startup if the MLflow
    server is slow or unreachable.
    """
    if not _is_configured():
        return

    from .core.config import settings

    # Configure auth before spawning the thread -- mlflow reads env vars directly.
    _configure_auth()

    if settings.MLFLOW_WORKSPACE:
        os.environ["MLFLOW_WORKSPACE"] = settings.MLFLOW_WORKSPACE
    if settings.MLFLOW_TRACKING_INSECURE_TLS:
        os.environ["MLFLOW_TRACKING_INSECURE_TLS"] = "true"

    thread = threading.Thread(target=_do_mlflow_init, daemon=True)
    thread.start()
    logger.info("MLFlow initialization started in background")


def set_trace_context(
    *,
    session_id: str,
    user_id: str | None = None,
    tags: list[str] | None = None,
) -> None:
    """Set MLFlow tags for trace correlation.

    Args:
        session_id: Correlates all messages within a WebSocket session.
        user_id: Optional user identifier attached to the trace.
        tags: Optional list of tags for filtering traces.

    Note:
        With autolog, traces are created automatically. This function sets
        tags on the active run for correlation and filtering in the MLFlow UI.
    """
    if not _autolog_enabled:
        return

    try:
        import mlflow

        mlflow.set_tag("session_id", session_id)
        if user_id:
            mlflow.set_tag("user_id", user_id)
        if tags:
            mlflow.set_tag("tags", ",".join(tags))
    except Exception:
        logger.debug("Failed to set MLFlow trace context", exc_info=True)


def log_observability_status() -> None:
    """Log whether MLFlow tracing is active or disabled. Call at startup."""
    from .core.config import settings

    if settings.MLFLOW_TRACKING_URI:
        status = "ACTIVE" if _autolog_enabled else "CONFIGURED (autolog pending)"
        logger.info(
            "MLFlow tracing: %s (uri=%s, experiment=%s)",
            status,
            settings.MLFLOW_TRACKING_URI,
            settings.MLFLOW_EXPERIMENT_NAME,
        )
    else:
        logger.info("MLFlow tracing: DISABLED (MLFLOW_TRACKING_URI not set)")
