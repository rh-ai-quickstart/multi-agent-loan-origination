# This project was developed with assistance from AI tools.
"""Tests for model monitoring service and endpoints (F39)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.model_monitoring import (
    ErrorMetrics,
    LatencyMetrics,
    ModelMonitoringSummary,
    RoutingDistribution,
    TokenUsage,
)
from src.services.model_monitoring import (
    compute_error_metrics,
    compute_latency_metrics,
    compute_routing_distribution,
    compute_token_usage,
    get_model_monitoring_summary,
)

# ---------------------------------------------------------------------------
# Synthetic observation factories
# ---------------------------------------------------------------------------


def _make_obs(
    model: str = "gpt-4o-mini",
    start_time: datetime | None = None,
    latency_ms: float = 500.0,
    input_tokens: int = 100,
    output_tokens: int = 50,
    level: str = "DEFAULT",
    status_message: str = "",
) -> dict:
    """Build a synthetic LangFuse observation dict."""
    if start_time is None:
        start_time = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    end_time = start_time + timedelta(milliseconds=latency_ms)
    return {
        "model": model,
        "startTime": start_time.isoformat(),
        "endTime": end_time.isoformat(),
        "usage": {"input": input_tokens, "output": output_tokens},
        "level": level,
        "statusMessage": status_message,
    }


def _make_observations(count: int = 10, **kwargs) -> list[dict]:
    """Build a list of synthetic observations with varying timestamps."""
    base = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
    return [_make_obs(start_time=base + timedelta(minutes=i * 10), **kwargs) for i in range(count)]


# ---------------------------------------------------------------------------
# Latency aggregation
# ---------------------------------------------------------------------------


class TestComputeLatencyMetrics:
    """Tests for compute_latency_metrics."""

    def test_should_compute_percentiles_from_observations(self):
        """Latency percentiles are calculated correctly."""
        obs = [_make_obs(latency_ms=ms) for ms in [100, 200, 300, 400, 500]]
        result = compute_latency_metrics(obs)

        assert isinstance(result, LatencyMetrics)
        assert result.p50_ms == 300.0
        assert result.p95_ms >= 400.0
        assert result.p99_ms >= 450.0

    def test_should_handle_empty_observations(self):
        """Empty observations yield zero percentiles."""
        result = compute_latency_metrics([])

        assert result.p50_ms == 0.0
        assert result.p95_ms == 0.0
        assert result.p99_ms == 0.0
        assert result.trend == []
        assert result.by_model == []

    def test_should_break_down_by_model(self):
        """Per-model breakdown groups latencies correctly."""
        obs = [
            _make_obs(model="model-a", latency_ms=100),
            _make_obs(model="model-a", latency_ms=200),
            _make_obs(model="model-b", latency_ms=500),
        ]
        result = compute_latency_metrics(obs)

        assert len(result.by_model) == 2
        model_a = next(m for m in result.by_model if m.model == "model-a")
        assert model_a.call_count == 2
        assert model_a.p50_ms == 150.0

    def test_should_produce_hourly_trend(self):
        """Observations spanning multiple hours produce trend points."""
        base = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
        obs = [
            _make_obs(start_time=base, latency_ms=100),
            _make_obs(start_time=base + timedelta(hours=1), latency_ms=200),
            _make_obs(start_time=base + timedelta(hours=2), latency_ms=300),
        ]
        result = compute_latency_metrics(obs)

        assert len(result.trend) == 3

    def test_should_handle_single_observation(self):
        """Single observation returns identical p50/p95/p99."""
        obs = [_make_obs(latency_ms=250.0)]
        result = compute_latency_metrics(obs)

        assert result.p50_ms == 250.0
        assert result.p95_ms == 250.0
        assert result.p99_ms == 250.0

    def test_should_skip_observations_without_timestamps(self):
        """Observations with missing start/end times are excluded."""
        obs = [
            {
                "model": "gpt-4o",
                "startTime": None,
                "endTime": None,
                "usage": {},
                "level": "DEFAULT",
            },
            _make_obs(latency_ms=200),
        ]
        result = compute_latency_metrics(obs)

        assert result.p50_ms == 200.0


# ---------------------------------------------------------------------------
# Token usage aggregation
# ---------------------------------------------------------------------------


class TestComputeTokenUsage:
    """Tests for compute_token_usage."""

    def test_should_sum_token_totals(self):
        """Token totals are summed across observations."""
        obs = _make_observations(3, input_tokens=100, output_tokens=50)
        result = compute_token_usage(obs)

        assert isinstance(result, TokenUsage)
        assert result.input_tokens == 300
        assert result.output_tokens == 150
        assert result.total_tokens == 450

    def test_should_handle_empty_observations(self):
        """Empty observations yield zero tokens."""
        result = compute_token_usage([])

        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.total_tokens == 0
        assert result.by_model == []

    def test_should_break_down_by_model(self):
        """Per-model breakdown groups tokens correctly."""
        obs = [
            _make_obs(model="model-a", input_tokens=100, output_tokens=50),
            _make_obs(model="model-b", input_tokens=200, output_tokens=100),
        ]
        result = compute_token_usage(obs)

        assert len(result.by_model) == 2
        model_b = next(m for m in result.by_model if m.model == "model-b")
        assert model_b.total_tokens == 300
        assert model_b.call_count == 1

    def test_should_handle_legacy_token_fields(self):
        """Observations with promptTokens/completionTokens are handled."""
        obs = [
            {
                "model": "legacy-model",
                "startTime": "2026-03-01T12:00:00+00:00",
                "endTime": "2026-03-01T12:00:01+00:00",
                "usage": {"promptTokens": 80, "completionTokens": 40},
                "level": "DEFAULT",
            }
        ]
        result = compute_token_usage(obs)

        assert result.input_tokens == 80
        assert result.output_tokens == 40

    def test_should_handle_null_usage(self):
        """Observations with usage=None yield zero tokens."""
        obs = [
            {
                "model": "model-a",
                "startTime": "2026-03-01T12:00:00+00:00",
                "endTime": "2026-03-01T12:00:01+00:00",
                "usage": None,
                "level": "DEFAULT",
            }
        ]
        result = compute_token_usage(obs)

        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.total_tokens == 0


# ---------------------------------------------------------------------------
# Error metrics aggregation
# ---------------------------------------------------------------------------


class TestComputeErrorMetrics:
    """Tests for compute_error_metrics."""

    def test_should_compute_error_rate(self):
        """Error rate is calculated from ERROR-level observations."""
        obs = [
            _make_obs(level="DEFAULT"),
            _make_obs(level="DEFAULT"),
            _make_obs(level="ERROR", status_message="timeout"),
        ]
        result = compute_error_metrics(obs)

        assert isinstance(result, ErrorMetrics)
        assert result.total_calls == 3
        assert result.error_count == 1
        assert result.error_rate == 33.33

    def test_should_handle_zero_errors(self):
        """No errors yields 0% error rate."""
        obs = _make_observations(5, level="DEFAULT")
        result = compute_error_metrics(obs)

        assert result.error_count == 0
        assert result.error_rate == 0.0
        assert result.top_errors == []

    def test_should_handle_empty_observations(self):
        """Empty observations yield zero metrics."""
        result = compute_error_metrics([])

        assert result.total_calls == 0
        assert result.error_count == 0
        assert result.error_rate == 0.0

    def test_should_rank_top_error_types(self):
        """Top error types are ranked by frequency."""
        obs = [
            _make_obs(level="ERROR", status_message="timeout"),
            _make_obs(level="ERROR", status_message="timeout"),
            _make_obs(level="ERROR", status_message="rate_limit"),
            _make_obs(level="DEFAULT"),
        ]
        result = compute_error_metrics(obs)

        assert result.error_count == 3
        assert len(result.top_errors) == 2
        assert result.top_errors[0].error_type == "timeout"
        assert result.top_errors[0].count == 2

    def test_should_detect_error_in_status_message(self):
        """Observations with 'error' in statusMessage are counted as errors."""
        obs = [
            _make_obs(level="DEFAULT", status_message="connection error occurred"),
        ]
        result = compute_error_metrics(obs)

        assert result.error_count == 1


# ---------------------------------------------------------------------------
# Routing distribution aggregation
# ---------------------------------------------------------------------------


class TestComputeRoutingDistribution:
    """Tests for compute_routing_distribution."""

    def test_should_compute_model_percentages(self):
        """Model routing percentages are calculated correctly."""
        obs = [
            _make_obs(model="model-a"),
            _make_obs(model="model-a"),
            _make_obs(model="model-a"),
            _make_obs(model="model-b"),
        ]
        result = compute_routing_distribution(obs)

        assert isinstance(result, RoutingDistribution)
        assert result.total_calls == 4
        assert len(result.models) == 2
        model_a = next(m for m in result.models if m.model == "model-a")
        assert model_a.call_count == 3
        assert model_a.percentage == 75.0

    def test_should_handle_empty_observations(self):
        """Empty observations yield zero distribution."""
        result = compute_routing_distribution([])

        assert result.total_calls == 0
        assert result.models == []

    def test_should_handle_unknown_model(self):
        """Observations without a model field are grouped as 'unknown'."""
        obs = [{"model": None, "startTime": None, "endTime": None, "usage": {}, "level": "DEFAULT"}]
        result = compute_routing_distribution(obs)

        assert result.models[0].model == "unknown"
        assert result.models[0].call_count == 1


# ---------------------------------------------------------------------------
# get_model_monitoring_summary -- orchestrator
# ---------------------------------------------------------------------------


class TestGetModelMonitoringSummary:
    """Tests for get_model_monitoring_summary."""

    @pytest.mark.asyncio
    async def test_should_return_demo_data_when_langfuse_not_configured(self):
        """When LangFuse is not configured, return demo metrics with langfuse_available=False."""
        with patch(
            "src.services.model_monitoring.fetch_observations", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = None
            result = await get_model_monitoring_summary(hours=24)

        assert isinstance(result, ModelMonitoringSummary)
        assert result.langfuse_available is False
        assert result.latency is not None
        assert result.token_usage is not None
        assert result.errors is not None
        assert result.routing is not None
        assert result.time_range_hours == 24

    @pytest.mark.asyncio
    async def test_should_return_metrics_when_observations_available(self):
        """When LangFuse returns data, all metric panels are populated."""
        obs = _make_observations(5)
        with patch(
            "src.services.model_monitoring.fetch_observations", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = obs
            result = await get_model_monitoring_summary(hours=24)

        assert result.langfuse_available is True
        assert result.latency is not None
        assert result.token_usage is not None
        assert result.errors is not None
        assert result.routing is not None

    @pytest.mark.asyncio
    async def test_should_pass_model_filter_to_fetch(self):
        """Model filter is forwarded to fetch_observations."""
        with patch(
            "src.services.model_monitoring.fetch_observations", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await get_model_monitoring_summary(hours=24, model="gpt-4o")

        _, kwargs = mock_fetch.call_args
        assert kwargs["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_should_raise_on_http_error(self):
        """HTTP errors from LangFuse are propagated."""
        import httpx

        with patch(
            "src.services.model_monitoring.fetch_observations", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Internal Server Error",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(500),
            )
            with pytest.raises(httpx.HTTPStatusError):
                await get_model_monitoring_summary(hours=24)


# ---------------------------------------------------------------------------
# REST endpoint tests
# ---------------------------------------------------------------------------


class TestModelMonitoringEndpoints:
    """Tests for /api/analytics/model-monitoring route layer."""

    def test_should_reject_invalid_hours(self, client):
        """GET /api/analytics/model-monitoring?hours=0 returns 422."""
        response = client.get("/api/analytics/model-monitoring", params={"hours": 0})
        assert response.status_code == 422

    def test_should_reject_hours_over_max(self, client):
        """GET /api/analytics/model-monitoring?hours=9999 returns 422."""
        response = client.get("/api/analytics/model-monitoring", params={"hours": 9999})
        assert response.status_code == 422


class TestModelMonitoringErrorHandling:
    """Route-layer error handling tests (503 paths not covered by functional tests)."""

    @pytest.fixture(autouse=True)
    def _clean(self):
        from src.main import app

        yield
        app.dependency_overrides.clear()

    def _make_client(self):
        """Build a TestClient with CEO persona."""
        from fastapi.testclient import TestClient

        from src.main import app
        from tests.functional.mock_db import configure_app_for_persona, make_mock_session
        from tests.functional.personas import ceo

        configure_app_for_persona(app, ceo(), make_mock_session())
        return TestClient(app)

    @patch("src.services.model_monitoring.fetch_observations", new_callable=AsyncMock)
    def test_should_return_503_on_langfuse_http_error(self, mock_fetch):
        """GET /api/analytics/model-monitoring returns 503 when LangFuse is down."""
        import httpx

        mock_fetch.side_effect = httpx.HTTPStatusError(
            "Service Unavailable",
            request=httpx.Request("GET", "http://test"),
            response=httpx.Response(503),
        )
        client = self._make_client()

        response = client.get("/api/analytics/model-monitoring")

        assert response.status_code == 503

    @patch("src.services.model_monitoring.fetch_observations", new_callable=AsyncMock)
    def test_should_return_503_on_connection_error(self, mock_fetch):
        """GET /api/analytics/model-monitoring returns 503 when LangFuse unreachable."""
        import httpx

        mock_fetch.side_effect = httpx.ConnectError("Connection refused")
        client = self._make_client()

        response = client.get("/api/analytics/model-monitoring")

        assert response.status_code == 503

    @patch("src.services.model_monitoring.fetch_observations", new_callable=AsyncMock)
    def test_should_return_demo_latency_when_langfuse_unconfigured(self, mock_fetch):
        """GET /api/analytics/model-monitoring/latency returns demo data when LangFuse not configured."""
        mock_fetch.return_value = None
        client = self._make_client()

        response = client.get("/api/analytics/model-monitoring/latency")

        assert response.status_code == 200
        data = response.json()
        assert "p50_ms" in data
