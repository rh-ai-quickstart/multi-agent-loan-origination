# This project was developed with assistance from AI tools.
"""LangGraph tools for compliance knowledge base search.

Provides the kb_search tool that agents can use to query the three-tier
compliance knowledge base (federal regulations, agency guidelines,
internal policies) with conflict detection and audit logging.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  See loan_officer_tools.py
    for rationale.
"""

import logging
from typing import Annotated

from db.database import SessionLocal
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..services.audit import write_audit_event
from ..services.compliance.knowledge_base.conflict import detect_conflicts
from ..services.compliance.knowledge_base.search import search_kb

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "\nThis content is simulated for demonstration purposes "
    "and does not constitute legal or regulatory advice."
)


@tool
async def kb_search(
    query: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Search the Summit Cap Financial compliance knowledge base for regulatory guidance.

    Searches federal regulations, agency guidelines, and internal policies
    using semantic similarity. Returns results ranked by relevance with
    tier-based priority (federal > agency > internal). Detects conflicts
    between sources automatically.

    Args:
        query: The regulatory or compliance question to search for.
        state: Injected agent state containing user context.
    """
    user_id = state.get("user_id", "anonymous")
    user_role = state.get("user_role", "")
    session_id = state.get("session_id")

    async with SessionLocal() as session:
        # Search the KB
        results = await search_kb(session, query)

        # Audit the search
        await write_audit_event(
            session,
            event_type="agent_tool_called",
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
            event_data={
                "tool": "kb_search",
                "query": query,
                "result_count": len(results),
            },
        )

        if not results:
            await session.commit()
            return (
                "No relevant compliance guidance found for that query. "
                "Could you rephrase your question or be more specific?" + _DISCLAIMER
            )

        # Detect conflicts
        conflicts = detect_conflicts(results)

        if conflicts:
            await write_audit_event(
                session,
                event_type="system",
                session_id=session_id,
                user_id=user_id,
                user_role=user_role,
                event_data={
                    "action": "kb_conflict_detected",
                    "query": query,
                    "conflict_count": len(conflicts),
                    "conflict_types": [c.conflict_type for c in conflicts],
                },
            )

        await session.commit()

    # Format output
    lines = [f"Compliance KB Search Results ({len(results)} found):\n"]

    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r.tier_label}]")
        lines.append(f"   Source: {r.source_document}")
        if r.section_ref:
            lines.append(f"   Section: {r.section_ref}")
        if r.effective_date:
            lines.append(f"   Effective: {r.effective_date}")
        lines.append(f"   {r.chunk_text[:500]}")
        lines.append("")

    if conflicts:
        lines.append("CONFLICTS DETECTED:")
        for c in conflicts:
            lines.append(f"  - {c.conflict_type.replace('_', ' ').title()}: {c.description}")
        lines.append("")

    lines.append(_DISCLAIMER)

    return "\n".join(lines)
