# This project was developed with assistance from AI tools.
"""LangGraph tools for the CEO executive assistant agent.

These wrap the Analytics and Audit services so the CEO agent can answer
pipeline, performance, denial, and audit questions conversationally.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  See loan_officer_tools.py for
    the rationale.
"""

from typing import Annotated

from db import Application, ApplicationBorrower, Borrower
from db.database import SessionLocal
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..services.analytics import get_denial_trends, get_lo_performance, get_pipeline_summary
from ..services.audit import (
    get_decision_trace,
    get_events_by_application,
    search_events,
    write_audit_event,
)
from ..services.model_monitoring import get_model_monitoring_summary
from .shared import user_context_from_state


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="ceo")


# ---------------------------------------------------------------------------
# Pipeline & performance tools (S-5-F13-06)
# ---------------------------------------------------------------------------


@tool
async def ceo_pipeline_summary(
    days: int = 90,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get pipeline summary: application counts by stage, pull-through rate, average days to close, and turn times.

    Args:
        days: Time range in days for historical metrics (default 90).
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        summary = await get_pipeline_summary(session, days=days)
        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_pipeline_summary", "days": days},
        )
        await session.commit()

    lines = [
        f"Pipeline Summary ({summary.time_range_days}-day window):",
        f"Total active applications: {summary.total_applications}",
        "",
        "By stage:",
    ]
    for sc in summary.by_stage:
        lines.append(f"  {sc.stage.replace('_', ' ').title()}: {sc.count}")

    lines.append("")
    lines.append(f"Pull-through rate: {summary.pull_through_rate}%")
    if summary.avg_days_to_close is not None:
        lines.append(f"Average days to close: {summary.avg_days_to_close}")

    if summary.turn_times:
        lines.append("")
        lines.append("Turn times:")
        for tt in summary.turn_times:
            from_label = tt.from_stage.replace("_", " ").title()
            to_label = tt.to_stage.replace("_", " ").title()
            lines.append(f"  {from_label} -> {to_label}: {tt.avg_days} days (n={tt.sample_size})")

    return "\n".join(lines)


@tool
async def ceo_denial_trends(
    days: int = 90,
    product: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get denial rate trends: overall rate, time-based trend, top reasons, and per-product breakdown.

    Args:
        days: Time range in days (default 90).
        product: Optional loan type filter (e.g. 'conventional_30', 'fha', 'va').
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        try:
            trends = await get_denial_trends(session, days=days, product=product)
        except ValueError as e:
            return str(e)

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_denial_trends", "days": days, "product": product},
        )
        await session.commit()

    lines = [
        f"Denial Trends ({trends.time_range_days}-day window):",
        f"Overall denial rate: {trends.overall_denial_rate}%",
        f"Total decisions: {trends.total_decisions}, Denials: {trends.total_denials}",
    ]

    if trends.trend:
        lines.append("")
        lines.append("Trend:")
        for pt in trends.trend:
            lines.append(f"  {pt.period}: {pt.denial_rate}% ({pt.denial_count}/{pt.total_decided})")

    if trends.top_reasons:
        lines.append("")
        lines.append("Top denial reasons:")
        for r in trends.top_reasons:
            lines.append(f"  {r.reason}: {r.count} ({r.percentage}%)")

    if trends.by_product:
        lines.append("")
        lines.append("By product:")
        for prod, rate in trends.by_product.items():
            lines.append(f"  {prod}: {rate}%")

    return "\n".join(lines)


@tool
async def ceo_lo_performance(
    days: int = 90,
    product: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get loan officer performance metrics: active pipeline, closed count, pull-through, turn times, denial rate.

    Args:
        days: Time range in days (default 90).
        product: Optional loan type filter (e.g. 'conventional_30', 'fha').
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        try:
            summary = await get_lo_performance(session, days=days, product=product)
        except ValueError as e:
            return str(e)

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_lo_performance", "days": days, "product": product},
        )
        await session.commit()

    if not summary.loan_officers:
        return "No loan officer data found for the specified period."

    lines = [f"Loan Officer Performance ({summary.time_range_days}-day window):", ""]
    for lo in summary.loan_officers:
        name = lo.lo_name or lo.lo_id
        lines.append(f"{name}:")
        lines.append(f"  Active pipeline: {lo.active_count}")
        lines.append(f"  Closed: {lo.closed_count}")
        lines.append(f"  Pull-through rate: {lo.pull_through_rate}%")
        lines.append(f"  Denial rate: {lo.denial_rate}%")
        if lo.avg_days_to_underwriting is not None:
            lines.append(f"  Avg days to underwriting: {lo.avg_days_to_underwriting}")
        if lo.avg_days_conditions_to_cleared is not None:
            lines.append(f"  Avg days conditions to cleared: {lo.avg_days_conditions_to_cleared}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Application & audit lookup tools (S-5-F13-08)
# ---------------------------------------------------------------------------


@tool
async def ceo_application_lookup(
    borrower_name: str | None = None,
    application_id: int | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Look up a loan application by borrower name or application ID.

    Returns current stage, assigned LO, loan details, and outstanding conditions.
    PII fields are masked by the middleware for CEO role.

    Args:
        borrower_name: Borrower's name to search for (partial match).
        application_id: Specific application ID to look up.
    """
    if not borrower_name and not application_id:
        return "Please provide either a borrower name or application ID."

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        eager = selectinload(Application.application_borrowers).joinedload(
            ApplicationBorrower.borrower
        )
        if application_id:
            stmt = select(Application).options(eager).where(Application.id == application_id)
        else:
            stmt = (
                select(Application)
                .options(eager)
                .join(ApplicationBorrower)
                .join(Borrower)
                .where((Borrower.first_name + " " + Borrower.last_name).ilike(f"%{borrower_name}%"))
            )

        result = await session.execute(stmt)
        apps = result.scalars().unique().all()

        if not apps:
            await write_audit_event(
                session,
                event_type="query",
                user_id=user.user_id,
                user_role=user.role.value,
                event_data={
                    "tool": "ceo_application_lookup",
                    "borrower_name": borrower_name,
                    "application_id": application_id,
                    "result": "not_found",
                },
            )
            await session.commit()
            if borrower_name:
                return (
                    f"No applications found for borrower matching '{borrower_name}'. "
                    "Try searching by application ID instead."
                )
            return f"Application {application_id} not found."

        # Format inside session to avoid DetachedInstanceError
        lines = []
        for app in apps:
            stage = app.stage.value if app.stage else "inquiry"
            lines.append(f"Application #{app.id}:")
            lines.append(f"  Stage: {stage.replace('_', ' ').title()}")
            if app.assigned_to:
                lines.append(f"  Assigned LO: {app.assigned_to}")
            if app.loan_type:
                lines.append(f"  Loan type: {app.loan_type.value}")
            if app.loan_amount:
                lines.append(f"  Loan amount: ${app.loan_amount:,.2f}")
            if app.property_address:
                lines.append(f"  Property: {app.property_address}")

            for ab in app.application_borrowers or []:
                if ab.borrower:
                    b = ab.borrower
                    role_label = "Primary" if ab.is_primary else "Co-borrower"
                    lines.append(f"  {role_label}: {b.first_name} {b.last_name}")

            lines.append("")

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={
                "tool": "ceo_application_lookup",
                "borrower_name": borrower_name,
                "application_id": application_id,
            },
        )
        await session.commit()

    return "\n".join(lines)


@tool
async def ceo_audit_trail(
    application_id: int,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get the audit trail for a specific application, showing all events in chronological order.

    Args:
        application_id: The application ID to get audit events for.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        events = await get_events_by_application(session, application_id)

        if not events:
            await write_audit_event(
                session,
                event_type="query",
                user_id=user.user_id,
                user_role=user.role.value,
                event_data={"tool": "ceo_audit_trail", "application_id": application_id},
            )
            await session.commit()
            return f"No audit events found for application {application_id}."

        # Format inside session to avoid DetachedInstanceError
        lines = [f"Audit trail for application #{application_id} ({len(events)} events):", ""]
        for evt in events:
            ts = str(evt.timestamp)[:19] if evt.timestamp else "?"
            line = f"  [{ts}] {evt.event_type}"
            if evt.user_id:
                line += f" (by {evt.user_id})"
            lines.append(line)

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_audit_trail", "application_id": application_id},
        )
        await session.commit()

    return "\n".join(lines)


@tool
async def ceo_decision_trace(
    decision_id: int,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get a backward trace from a specific underwriting decision to all contributing events.

    Shows decision metadata, rationale, AI recommendation, and all audit events
    that led to the decision, grouped by type.

    Args:
        decision_id: The decision ID to trace.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        trace = await get_decision_trace(session, decision_id)

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_decision_trace", "decision_id": decision_id},
        )
        await session.commit()

    if trace is None:
        return f"Decision {decision_id} not found."

    lines = [
        f"Decision #{trace['decision_id']} Trace:",
        f"  Application: #{trace['application_id']}",
    ]
    if trace.get("decision_type"):
        lines.append(f"  Type: {trace['decision_type']}")
    if trace.get("decided_by"):
        lines.append(f"  Decided by: {trace['decided_by']}")
    if trace.get("rationale"):
        lines.append(f"  Rationale: {trace['rationale']}")
    if trace.get("ai_recommendation"):
        lines.append(f"  AI recommendation: {trace['ai_recommendation']}")
    if trace.get("ai_agreement") is not None:
        lines.append(f"  AI agreement: {'Yes' if trace['ai_agreement'] else 'No'}")
    if trace.get("override_rationale"):
        lines.append(f"  Override rationale: {trace['override_rationale']}")

    events_by_type = trace.get("events_by_type", {})
    if events_by_type:
        lines.append("")
        lines.append(f"Contributing events ({trace.get('total_events', 0)} total):")
        for event_type, events in events_by_type.items():
            lines.append(f"  {event_type}: {len(events)} event(s)")

    return "\n".join(lines)


@tool
async def ceo_audit_search(
    days: int | None = None,
    event_type: str | None = None,
    limit: int = 100,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Search audit events by time range and/or event type.

    Args:
        days: Time range in days (e.g. 7 for last week, 30 for last month).
        event_type: Filter by event type (e.g. 'stage_transition', 'decision_rendered').
        limit: Maximum events to return (default 100).
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        events = await search_events(session, days=days, event_type=event_type, limit=limit)

        if not events:
            await write_audit_event(
                session,
                event_type="query",
                user_id=user.user_id,
                user_role=user.role.value,
                event_data={
                    "tool": "ceo_audit_search",
                    "days": days,
                    "event_type": event_type,
                    "limit": limit,
                },
            )
            await session.commit()
            return "No audit events found matching the criteria."

        # Format inside session to avoid DetachedInstanceError
        lines = [f"Audit search results ({len(events)} events):"]
        if days:
            lines[0] += f" (last {days} days)"
        if event_type:
            lines[0] += f" (type: {event_type})"
        lines.append("")

        for evt in events[:50]:  # Cap display at 50 for readability
            ts = str(evt.timestamp)[:19] if evt.timestamp else "?"
            line = f"  [{ts}] {evt.event_type}"
            if evt.application_id:
                line += f" (app #{evt.application_id})"
            if evt.user_id:
                line += f" by {evt.user_id}"
            lines.append(line)

        if len(events) > 50:
            lines.append(f"  ... and {len(events) - 50} more events")

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={
                "tool": "ceo_audit_search",
                "days": days,
                "event_type": event_type,
                "limit": limit,
            },
        )
        await session.commit()

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Model monitoring tools (S-5-F39)
# ---------------------------------------------------------------------------


@tool
async def ceo_model_latency(
    hours: int = 24,
    model: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get model latency percentiles (p50, p95, p99) and trend.

    Args:
        hours: Time range in hours (default 24).
        model: Optional model name filter.
    """
    user = _user_context_from_state(state)
    try:
        summary = await get_model_monitoring_summary(hours=hours, model=model)
    except Exception as e:
        return f"Error fetching model monitoring data: {e}"

    async with SessionLocal() as session:
        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_model_latency", "hours": hours, "model": model},
        )
        await session.commit()

    if not summary.mlflow_available:
        return "Model monitoring unavailable (MLflow not configured)."

    lat = summary.latency
    lines = [
        f"Model Latency ({summary.time_range_hours}h window):",
        f"  p50: {lat.p50_ms:.1f}ms",
        f"  p95: {lat.p95_ms:.1f}ms",
        f"  p99: {lat.p99_ms:.1f}ms",
    ]
    if lat.by_model:
        lines.append("")
        lines.append("By model:")
        for m in lat.by_model:
            lines.append(
                f"  {m.model}: p50={m.p50_ms:.1f}ms, p95={m.p95_ms:.1f}ms ({m.call_count} calls)"
            )
    return "\n".join(lines)


@tool
async def ceo_model_token_usage(
    hours: int = 24,
    model: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get token usage totals and per-model breakdown.

    Args:
        hours: Time range in hours (default 24).
        model: Optional model name filter.
    """
    user = _user_context_from_state(state)
    try:
        summary = await get_model_monitoring_summary(hours=hours, model=model)
    except Exception as e:
        return f"Error fetching model monitoring data: {e}"

    async with SessionLocal() as session:
        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={
                "tool": "ceo_model_token_usage",
                "hours": hours,
                "model": model,
            },
        )
        await session.commit()

    if not summary.mlflow_available:
        return "Model monitoring unavailable (MLflow not configured)."

    tok = summary.token_usage
    lines = [
        f"Token Usage ({summary.time_range_hours}h window):",
        f"  Input tokens: {tok.input_tokens:,}",
        f"  Output tokens: {tok.output_tokens:,}",
        f"  Total tokens: {tok.total_tokens:,}",
    ]
    if tok.by_model:
        lines.append("")
        lines.append("By model:")
        for m in tok.by_model:
            lines.append(f"  {m.model}: {m.total_tokens:,} tokens ({m.call_count} calls)")
    return "\n".join(lines)


@tool
async def ceo_model_errors(
    hours: int = 24,
    model: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get model error rates and top error types.

    Args:
        hours: Time range in hours (default 24).
        model: Optional model name filter.
    """
    user = _user_context_from_state(state)
    try:
        summary = await get_model_monitoring_summary(hours=hours, model=model)
    except Exception as e:
        return f"Error fetching model monitoring data: {e}"

    async with SessionLocal() as session:
        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_model_errors", "hours": hours, "model": model},
        )
        await session.commit()

    if not summary.mlflow_available:
        return "Model monitoring unavailable (MLflow not configured)."

    err = summary.errors
    lines = [
        f"Model Errors ({summary.time_range_hours}h window):",
        f"  Total calls: {err.total_calls:,}",
        f"  Error count: {err.error_count:,}",
        f"  Error rate: {err.error_rate}%",
    ]
    if err.top_errors:
        lines.append("")
        lines.append("Top error types:")
        for e in err.top_errors[:5]:
            lines.append(f"  {e.error_type}: {e.count}")
    return "\n".join(lines)


@tool
async def ceo_model_routing(
    hours: int = 24,
    model: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get model routing distribution showing which models handle what percentage of calls.

    Args:
        hours: Time range in hours (default 24).
        model: Optional model name filter.
    """
    user = _user_context_from_state(state)
    try:
        summary = await get_model_monitoring_summary(hours=hours, model=model)
    except Exception as e:
        return f"Error fetching model monitoring data: {e}"

    async with SessionLocal() as session:
        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_model_routing", "hours": hours, "model": model},
        )
        await session.commit()

    if not summary.mlflow_available:
        return "Model monitoring unavailable (MLflow not configured)."

    routing = summary.routing
    lines = [
        f"Model Routing ({summary.time_range_hours}h window):",
        f"  Total calls: {routing.total_calls:,}",
        "",
        "Distribution:",
    ]
    for m in routing.models:
        lines.append(f"  {m.model}: {m.call_count:,} calls ({m.percentage}%)")
    return "\n".join(lines)
