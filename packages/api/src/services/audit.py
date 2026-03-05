# This project was developed with assistance from AI tools.
"""Audit event service.

Writes append-only audit trail entries with SHA-256 hash chain for tamper
evidence (S-2-F15-04) and PostgreSQL advisory lock for serial hash
computation (S-2-F15-05).  Session_id enables LangFuse trace correlation
(S-1-F18-03).
"""

import csv
import hashlib
import io
import json
import logging
from datetime import UTC, datetime, timedelta

from db import AuditEvent, Decision
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Fixed advisory lock key for audit trail serialization.
# Only audit event inserts are serialized; other DB operations are unaffected.
AUDIT_LOCK_KEY = 900_001


def _compute_hash(
    event_id: int,
    timestamp: str,
    event_type: str,
    user_id: str | None,
    user_role: str | None,
    application_id: int | None,
    session_id: str | None,
    event_data: dict | None,
) -> str:
    """Compute SHA-256 hash of an audit event's key fields.

    Includes all audit fields for stronger tamper evidence:
    - event_id, timestamp, event_type
    - user_id, user_role, application_id, session_id
    - event_data (JSON serialized)
    """
    payload = (
        f"{event_id}|{timestamp}|{event_type}|"
        f"{user_id or ''}|{user_role or ''}|{application_id or ''}|"
        f"{session_id or ''}|{json.dumps(event_data, sort_keys=True, default=str)}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def write_audit_event(
    session: AsyncSession,
    *,
    event_type: str,
    session_id: str | None = None,
    user_id: str | None = None,
    user_role: str | None = None,
    application_id: int | None = None,
    event_data: dict | None = None,
) -> AuditEvent:
    """Write a single audit event with hash chain linkage.

    Acquires a PostgreSQL advisory lock to serialize hash computation,
    then computes prev_hash from the most recent event.

    Args:
        session: Database session.
        event_type: Event category (e.g. 'agent_tool_called', 'safety_block').
        session_id: WebSocket/LangFuse session ID for trace correlation.
        user_id: User who triggered the event.
        user_role: Role at the time of the event.
        application_id: Related application, if any.
        event_data: Arbitrary JSON-serializable event payload.

    Returns:
        The created AuditEvent row (with prev_hash set).
    """
    # Advisory lock serializes hash chain computation across concurrent writers.
    # Released automatically when the transaction commits or rolls back.
    await session.execute(text(f"SELECT pg_advisory_xact_lock({AUDIT_LOCK_KEY})"))

    # Fetch the most recent event for hash chain linkage.
    latest_stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)
    result = await session.execute(latest_stmt)
    prev_event = result.scalar_one_or_none()

    if prev_event is not None:
        prev_hash = _compute_hash(
            prev_event.id,
            str(prev_event.timestamp),
            prev_event.event_type,
            prev_event.user_id,
            prev_event.user_role,
            prev_event.application_id,
            prev_event.session_id,
            prev_event.event_data,
        )
    else:
        prev_hash = "genesis"

    audit = AuditEvent(
        event_type=event_type,
        session_id=session_id,
        user_id=user_id,
        user_role=user_role,
        application_id=application_id,
        event_data=event_data,
        prev_hash=prev_hash,
    )
    session.add(audit)
    await session.flush()
    return audit


async def verify_audit_chain(session: AsyncSession) -> dict:
    """Verify the integrity of the audit event hash chain.

    Walks all events in ID order, recomputes each expected prev_hash,
    and compares against the stored value.

    Returns:
        {"status": "OK", "events_checked": N} on success, or
        {"status": "TAMPERED", "first_break_id": id, "events_checked": N}
        if a mismatch is found.
    """
    stmt = select(AuditEvent).order_by(AuditEvent.id.asc())
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    if not events:
        return {"status": "OK", "events_checked": 0}

    for i, event in enumerate(events):
        if i == 0:
            expected = "genesis"
        else:
            prev = events[i - 1]
            expected = _compute_hash(
                prev.id,
                str(prev.timestamp),
                prev.event_type,
                prev.user_id,
                prev.user_role,
                prev.application_id,
                prev.session_id,
                prev.event_data,
            )

        if event.prev_hash != expected:
            return {
                "status": "TAMPERED",
                "first_break_id": event.id,
                "events_checked": i + 1,
            }

    return {"status": "OK", "events_checked": len(events)}


async def get_audit_chain_length(session: AsyncSession) -> int:
    """Return the total number of audit events."""
    result = await session.execute(select(func.count(AuditEvent.id)))
    return result.scalar_one()


async def get_events_by_session(
    session: AsyncSession,
    session_id: str,
) -> list[AuditEvent]:
    """Return all audit events for a given session_id.

    This is the compliance-side query for trace-audit correlation:
    given a session_id from LangFuse, retrieve all audit events.
    """
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.session_id == session_id)
        .order_by(AuditEvent.timestamp.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_events_by_application(
    session: AsyncSession,
    application_id: int,
) -> list[AuditEvent]:
    """Return all audit events for a given application_id.

    This is the compliance-side query for per-loan audit trail review:
    given an application_id, retrieve every audit event (stage transitions,
    document flags, communications, etc.) in chronological order.
    """
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.application_id == application_id)
        .order_by(AuditEvent.timestamp.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# CEO audit trail queries (S-5-F13-01 to S-5-F13-05, S-5-F15-07)
# ---------------------------------------------------------------------------


async def get_events_by_decision(
    session: AsyncSession,
    decision_id: int,
) -> list[AuditEvent]:
    """Return all audit events linked to a decision (backward trace).

    Finds the decision's application_id, then returns all events for that
    application -- giving full context from creation through decision.
    """
    dec = await session.get(Decision, decision_id)
    if dec is None:
        return []

    stmt = (
        select(AuditEvent)
        .where(AuditEvent.application_id == dec.application_id)
        .order_by(AuditEvent.timestamp.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_events(
    session: AsyncSession,
    *,
    days: int | None = None,
    event_type: str | None = None,
    limit: int = 500,
) -> list[AuditEvent]:
    """Search audit events by time range and/or event type."""
    stmt = select(AuditEvent)

    if days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = stmt.where(AuditEvent.timestamp >= cutoff)

    if event_type is not None:
        stmt = stmt.where(AuditEvent.event_type == event_type)

    stmt = stmt.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_decision_trace(
    session: AsyncSession,
    decision_id: int,
) -> dict | None:
    """Build a structured backward trace from a decision.

    Returns the decision record plus all contributing audit events grouped
    by category, or None if the decision doesn't exist.
    """
    dec = await session.get(Decision, decision_id)
    if dec is None:
        return None

    events = await get_events_by_application(session, dec.application_id)

    grouped: dict[str, list] = {}
    for evt in events:
        grouped.setdefault(evt.event_type, []).append(
            {
                "id": evt.id,
                "timestamp": evt.timestamp.isoformat() if evt.timestamp else None,
                "user_id": evt.user_id,
                "user_role": evt.user_role,
                "event_data": evt.event_data,
            }
        )

    return {
        "decision_id": dec.id,
        "application_id": dec.application_id,
        "decision_type": dec.decision_type.value if dec.decision_type else None,
        "rationale": dec.rationale,
        "ai_recommendation": dec.ai_recommendation,
        "ai_agreement": dec.ai_agreement,
        "override_rationale": dec.override_rationale,
        "denial_reasons": dec.denial_reasons,
        "decided_by": dec.decided_by,
        "events_by_type": grouped,
        "total_events": len(events),
    }


# ---------------------------------------------------------------------------
# Audit export (S-5-F15-07)
# ---------------------------------------------------------------------------

_EXPORT_COLUMNS = [
    "event_id",
    "timestamp",
    "event_type",
    "user_id",
    "user_role",
    "application_id",
    "event_data",
    "prev_hash",
]


def _event_to_export_row(evt: AuditEvent) -> dict:
    """Convert an AuditEvent to a flat export dict."""
    return {
        "event_id": evt.id,
        "timestamp": evt.timestamp.isoformat() if evt.timestamp else None,
        "event_type": evt.event_type,
        "user_id": evt.user_id,
        "user_role": evt.user_role,
        "application_id": evt.application_id,
        "event_data": json.dumps(evt.event_data, default=str) if evt.event_data else None,
        "prev_hash": evt.prev_hash,
    }


async def export_events(
    session: AsyncSession,
    *,
    fmt: str = "json",
    application_id: int | None = None,
    days: int | None = None,
    limit: int = 10_000,
    pii_mask: bool = False,
) -> tuple[str, str]:
    """Export audit events as JSON or CSV.

    Returns (content_string, media_type).
    When ``pii_mask`` is True, PII fields in ``event_data`` are masked before
    serialization (covers CSV path which bypasses the HTTP PII middleware).
    """
    from ..middleware.pii import _mask_pii_recursive

    stmt = select(AuditEvent)

    if application_id is not None:
        stmt = stmt.where(AuditEvent.application_id == application_id)
    if days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = stmt.where(AuditEvent.timestamp >= cutoff)

    stmt = stmt.order_by(AuditEvent.timestamp.asc()).limit(limit)
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    rows = [_event_to_export_row(e) for e in events]

    if pii_mask:
        rows = [_mask_pii_recursive(row) for row in rows]

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue(), "text/csv"

    return json.dumps(rows, indent=2, default=str), "application/json"
