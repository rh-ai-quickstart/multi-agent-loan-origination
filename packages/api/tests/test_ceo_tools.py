# This project was developed with assistance from AI tools.
"""Tests for CEO executive assistant tools (S-5-F13-06, F13-07, F13-08)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.analytics import (
    DenialReason,
    DenialTrendPoint,
    DenialTrends,
    LOPerformanceRow,
    LOPerformanceSummary,
    PipelineSummary,
    StageCount,
    StageTurnTime,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CEO_STATE = {
    "user_id": "ceo-001",
    "user_role": "ceo",
    "user_email": "ceo@example.com",
    "user_name": "CEO User",
}

_NOW = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)


def _mock_session_ctx():
    """Create an async context manager that yields a mock session."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, mock_session


# ---------------------------------------------------------------------------
# ceo_pipeline_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.get_pipeline_summary")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_pipeline_summary_returns_formatted_output(
    mock_audit, mock_get_pipeline, mock_session_cls
):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_get_pipeline.return_value = PipelineSummary(
        total_applications=42,
        by_stage=[
            StageCount(stage="application", count=10),
            StageCount(stage="underwriting", count=15),
            StageCount(stage="closed", count=17),
        ],
        pull_through_rate=40.5,
        avg_days_to_close=28.3,
        turn_times=[
            StageTurnTime(
                from_stage="application", to_stage="underwriting", avg_days=5.2, sample_size=8
            ),
        ],
        time_range_days=90,
        computed_at=_NOW,
    )

    from src.agents.ceo_tools import ceo_pipeline_summary

    result = await ceo_pipeline_summary.ainvoke({"days": 90, "state": _CEO_STATE})

    assert "Pipeline Summary (90-day window)" in result
    assert "Total active applications: 42" in result
    assert "Pull-through rate: 40.5%" in result
    assert "Average days to close: 28.3" in result
    assert "Application -> Underwriting: 5.2 days" in result
    mock_audit.assert_called_once()


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.get_pipeline_summary")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_pipeline_summary_no_turn_times(mock_audit, mock_get_pipeline, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_get_pipeline.return_value = PipelineSummary(
        total_applications=5,
        by_stage=[StageCount(stage="application", count=5)],
        pull_through_rate=0.0,
        avg_days_to_close=None,
        turn_times=[],
        time_range_days=30,
        computed_at=_NOW,
    )

    from src.agents.ceo_tools import ceo_pipeline_summary

    result = await ceo_pipeline_summary.ainvoke({"days": 30, "state": _CEO_STATE})

    assert "Pull-through rate: 0.0%" in result
    assert "Turn times" not in result
    assert "Average days to close" not in result


# ---------------------------------------------------------------------------
# ceo_denial_trends
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.get_denial_trends")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_denial_trends_returns_formatted_output(
    mock_audit, mock_get_denial, mock_session_cls
):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_get_denial.return_value = DenialTrends(
        overall_denial_rate=15.0,
        total_decisions=20,
        total_denials=3,
        trend=[
            DenialTrendPoint(period="2026-01", denial_rate=10.0, denial_count=1, total_decided=10),
            DenialTrendPoint(period="2026-02", denial_rate=20.0, denial_count=2, total_decided=10),
        ],
        top_reasons=[DenialReason(reason="High DTI", count=2, percentage=66.7)],
        by_product={"conventional_30": 12.0, "fha": 20.0},
        time_range_days=90,
        computed_at=_NOW,
    )

    from src.agents.ceo_tools import ceo_denial_trends

    result = await ceo_denial_trends.ainvoke({"days": 90, "state": _CEO_STATE})

    assert "Overall denial rate: 15.0%" in result
    assert "High DTI: 2 (66.7%)" in result
    assert "conventional_30: 12.0%" in result


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.get_denial_trends")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_denial_trends_invalid_product(mock_audit, mock_get_denial, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_get_denial.side_effect = ValueError("Unknown product 'invalid'")

    from src.agents.ceo_tools import ceo_denial_trends

    result = await ceo_denial_trends.ainvoke({"product": "invalid", "state": _CEO_STATE})

    assert "Unknown product" in result


# ---------------------------------------------------------------------------
# ceo_lo_performance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.get_lo_performance")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_lo_performance_returns_formatted_output(mock_audit, mock_get_lo, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_get_lo.return_value = LOPerformanceSummary(
        loan_officers=[
            LOPerformanceRow(
                lo_id="lo-james",
                lo_name="James Torres",
                active_count=8,
                closed_count=12,
                pull_through_rate=60.0,
                avg_days_to_underwriting=4.5,
                avg_days_conditions_to_cleared=3.2,
                denial_rate=8.3,
            ),
        ],
        time_range_days=90,
        computed_at=_NOW,
    )

    from src.agents.ceo_tools import ceo_lo_performance

    result = await ceo_lo_performance.ainvoke({"days": 90, "state": _CEO_STATE})

    assert "James Torres" in result
    assert "Active pipeline: 8" in result
    assert "Pull-through rate: 60.0%" in result
    assert "Denial rate: 8.3%" in result


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.get_lo_performance")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_lo_performance_no_data(mock_audit, mock_get_lo, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_get_lo.return_value = LOPerformanceSummary(
        loan_officers=[],
        time_range_days=90,
        computed_at=_NOW,
    )

    from src.agents.ceo_tools import ceo_lo_performance

    result = await ceo_lo_performance.ainvoke({"days": 90, "state": _CEO_STATE})

    assert "No loan officer data found" in result


# ---------------------------------------------------------------------------
# ceo_application_lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_application_lookup_by_id(mock_audit, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_app = MagicMock()
    mock_app.id = 100
    mock_app.stage = MagicMock(value="underwriting")
    mock_app.assigned_to = "lo-james"
    mock_app.loan_type = MagicMock(value="conventional_30")
    mock_app.loan_amount = 350000.0
    mock_app.property_address = "123 Main St"
    mock_app.application_borrowers = []

    mock_result = MagicMock()
    mock_result.scalars.return_value.unique.return_value.all.return_value = [mock_app]
    mock_session.execute = AsyncMock(return_value=mock_result)

    from src.agents.ceo_tools import ceo_application_lookup

    result = await ceo_application_lookup.ainvoke({"application_id": 100, "state": _CEO_STATE})

    assert "Application #100" in result
    assert "Underwriting" in result
    assert "lo-james" in result


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_application_lookup_not_found(mock_audit, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_result = MagicMock()
    mock_result.scalars.return_value.unique.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    from src.agents.ceo_tools import ceo_application_lookup

    result = await ceo_application_lookup.ainvoke({"borrower_name": "Nobody", "state": _CEO_STATE})

    assert "No applications found" in result
    assert "Try searching by application ID" in result


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_application_lookup_no_params(mock_audit, mock_session_cls):
    from src.agents.ceo_tools import ceo_application_lookup

    result = await ceo_application_lookup.ainvoke({"state": _CEO_STATE})

    assert "Please provide either" in result


# ---------------------------------------------------------------------------
# ceo_audit_trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.get_events_by_application")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_audit_trail_returns_events(mock_audit, mock_get_events, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    evt = MagicMock()
    evt.timestamp = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
    evt.event_type = "application_created"
    evt.user_id = "lo-james"
    mock_get_events.return_value = [evt]

    from src.agents.ceo_tools import ceo_audit_trail

    result = await ceo_audit_trail.ainvoke({"application_id": 100, "state": _CEO_STATE})

    assert "Audit trail for application #100" in result
    assert "application_created" in result
    assert "lo-james" in result


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.get_events_by_application")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_audit_trail_empty(mock_audit, mock_get_events, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_get_events.return_value = []

    from src.agents.ceo_tools import ceo_audit_trail

    result = await ceo_audit_trail.ainvoke({"application_id": 999, "state": _CEO_STATE})

    assert "No audit events found" in result


# ---------------------------------------------------------------------------
# ceo_decision_trace
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.get_decision_trace")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_decision_trace_returns_formatted(mock_audit, mock_get_trace, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_get_trace.return_value = {
        "decision_id": 5,
        "application_id": 100,
        "decision_type": "approved",
        "decided_by": "uw-001",
        "rationale": "Strong financials",
        "ai_recommendation": "approve",
        "ai_agreement": True,
        "override_rationale": None,
        "events_by_type": {
            "stage_transition": [1, 2],
            "compliance_check": [3],
        },
        "total_events": 3,
    }

    from src.agents.ceo_tools import ceo_decision_trace

    result = await ceo_decision_trace.ainvoke({"decision_id": 5, "state": _CEO_STATE})

    assert "Decision #5 Trace" in result
    assert "Application: #100" in result
    assert "Strong financials" in result
    assert "AI agreement: Yes" in result
    assert "stage_transition: 2 event(s)" in result


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.get_decision_trace")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_decision_trace_not_found(mock_audit, mock_get_trace, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_get_trace.return_value = None

    from src.agents.ceo_tools import ceo_decision_trace

    result = await ceo_decision_trace.ainvoke({"decision_id": 999, "state": _CEO_STATE})

    assert "Decision 999 not found" in result


# ---------------------------------------------------------------------------
# ceo_audit_search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.search_events")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_audit_search_returns_results(mock_audit, mock_search, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    evt = MagicMock()
    evt.timestamp = datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC)
    evt.event_type = "stage_transition"
    evt.application_id = 100
    evt.user_id = "lo-james"
    mock_search.return_value = [evt]

    from src.agents.ceo_tools import ceo_audit_search

    result = await ceo_audit_search.ainvoke(
        {"days": 7, "event_type": "stage_transition", "state": _CEO_STATE}
    )

    assert "Audit search results (1 events)" in result
    assert "stage_transition" in result
    assert "app #100" in result


@pytest.mark.asyncio
@patch("src.agents.ceo_tools.SessionLocal")
@patch("src.agents.ceo_tools.search_events")
@patch("src.agents.ceo_tools.write_audit_event", new_callable=AsyncMock)
async def test_audit_search_no_results(mock_audit, mock_search, mock_session_cls):
    ctx, mock_session = _mock_session_ctx()
    mock_session_cls.return_value = ctx

    mock_search.return_value = []

    from src.agents.ceo_tools import ceo_audit_search

    result = await ceo_audit_search.ainvoke({"days": 1, "state": _CEO_STATE})

    assert "No audit events found" in result


# ---------------------------------------------------------------------------
# Chat endpoint registration
# ---------------------------------------------------------------------------


def test_ceo_chat_router_registered():
    """CEO chat router should have WebSocket and history routes."""
    from src.routes.ceo_chat import router

    paths = [r.path for r in router.routes]
    assert "/ceo/chat" in paths
    assert "/ceo/conversations/history" in paths


def test_ceo_agent_registered():
    """CEO assistant should be in the agent registry."""
    from src.agents.registry import _AGENT_MODULES

    assert "ceo-assistant" in _AGENT_MODULES


def test_ceo_agent_config_exists():
    """YAML config file for ceo-assistant should exist."""
    from src.agents.registry import load_agent_config

    config = load_agent_config("ceo-assistant")
    assert config["agent"]["name"] == "ceo_assistant"
    assert config["agent"]["persona"] == "ceo"
