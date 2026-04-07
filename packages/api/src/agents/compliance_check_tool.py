# This project was developed with assistance from AI tools.
"""LangGraph tool for running compliance checks (ECOA, ATR/QM, TRID).

Wraps the pure compliance check functions with DB access to gather
application data, then formats results for the underwriter agent.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  See underwriter_tools.py
    for rationale.
"""

import logging
from typing import Annotated

from db.database import SessionLocal
from db.enums import ApplicationStage, DocumentType
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..services.application import get_application, get_financials
from ..services.audit import write_audit_event
from ..services.compliance.checks import (
    check_atr_qm,
    check_ecoa,
    check_trid,
    run_all_checks,
)
from ..services.compliance_result import create_compliance_result
from ..services.document import list_documents
from .shared import format_enum_label, resolve_app_id, user_context_from_state

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "\nDISCLAIMER: All regulatory information is simulated for demonstration "
    "purposes and does not constitute legal or regulatory advice."
)

_INCOME_DOC_TYPES = frozenset({DocumentType.W2, DocumentType.PAY_STUB, DocumentType.TAX_RETURN})
_ASSET_DOC_TYPES = frozenset({DocumentType.BANK_STATEMENT})
_EMPLOYMENT_DOC_TYPES = frozenset({DocumentType.W2, DocumentType.PAY_STUB})


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="underwriter")


def _format_check_result(check) -> list[str]:
    """Format a single ComplianceCheckResult into output lines."""
    lines = [
        f"  Status: {check.status.value}",
        f"  Rationale: {check.rationale}",
    ]
    if check.details:
        lines.append("  Details:")
        for d in check.details:
            lines.append(f"    - {d}")
    return lines


@tool
async def compliance_check(
    application_id: int,
    regulation_type: str = "ALL",
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Run compliance checks (ECOA, ATR/QM, TRID) on a loan application.

    Validates regulatory compliance for applications in the underwriting
    stage. Can run individual checks or all three combined.

    Args:
        application_id: The loan application ID to check.
        regulation_type: Which check to run -- "ECOA", "ATR_QM", "TRID", or "ALL".
    """
    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)
    regulation_type = regulation_type.upper().strip()

    valid_types = {"ECOA", "ATR_QM", "TRID", "ALL"}
    if regulation_type not in valid_types:
        return (
            f"Invalid regulation_type '{regulation_type}'. "
            f"Must be one of: {', '.join(sorted(valid_types))}"
        )

    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return f"Application #{application_id} not found or you don't have access to it."

        if app.stage != ApplicationStage.UNDERWRITING:
            stage_val = app.stage.value if app.stage else "unknown"
            await write_audit_event(
                session,
                event_type="agent_tool_called",
                user_id=user.user_id,
                user_role=user.role.value,
                application_id=application_id,
                event_data={
                    "tool": "compliance_check",
                    "error": f"wrong_stage:{stage_val}",
                },
            )
            await session.commit()
            return (
                f"Compliance checks are only available for applications in the "
                f"UNDERWRITING stage. Application #{application_id} is in "
                f"{format_enum_label(stage_val)}."
            )

        # Gather data for checks
        financials = await get_financials(session, application_id)

        documents, _ = await list_documents(session, user, application_id, limit=100)

        # Compute ATR/QM inputs
        total_income = sum(float(f.gross_monthly_income or 0) for f in financials)
        total_debts = sum(float(f.monthly_debts or 0) for f in financials)
        dti = total_debts / total_income if total_income > 0 else None

        doc_types = set()
        for doc in documents:
            dt = doc.doc_type if hasattr(doc.doc_type, "value") else None
            if dt:
                doc_types.add(dt)

        has_income_docs = bool(doc_types & _INCOME_DOC_TYPES)
        has_asset_docs = bool(doc_types & _ASSET_DOC_TYPES)
        has_employment_docs = bool(doc_types & _EMPLOYMENT_DOC_TYPES)

        # Run requested checks
        results = {}

        if regulation_type in ("ECOA", "ALL"):
            # ECOA compliance: demographics are isolated in hmda schema and never
            # accessible during underwriting. has_demographic_query=False indicates
            # no attempt was made to access protected data, which is correct by design.
            results["ECOA"] = check_ecoa(has_demographic_query=False)

        if regulation_type in ("ATR_QM", "ALL"):
            results["ATR_QM"] = check_atr_qm(
                dti=dti,
                has_income_docs=has_income_docs,
                has_asset_docs=has_asset_docs,
                has_employment_docs=has_employment_docs,
            )

        if regulation_type in ("TRID", "ALL"):
            results["TRID"] = check_trid(
                le_delivery_date=app.le_delivery_date,
                app_created_at=app.created_at,
                cd_delivery_date=app.cd_delivery_date,
                closing_date=app.closing_date,
            )

        # Run combined if ALL
        combined = None
        if regulation_type == "ALL" and len(results) == 3:
            combined = run_all_checks(results["ECOA"], results["ATR_QM"], results["TRID"])

        # Persist compliance result
        ecoa = results.get("ECOA")
        atr_qm = results.get("ATR_QM")
        trid = results.get("TRID")
        await create_compliance_result(
            session,
            application_id=application_id,
            ecoa_status=ecoa.status.value if ecoa else None,
            ecoa_rationale=ecoa.rationale if ecoa else None,
            ecoa_details=ecoa.details if ecoa else None,
            atr_qm_status=atr_qm.status.value if atr_qm else None,
            atr_qm_rationale=atr_qm.rationale if atr_qm else None,
            atr_qm_details=atr_qm.details if atr_qm else None,
            trid_status=trid.status.value if trid else None,
            trid_rationale=trid.rationale if trid else None,
            trid_details=trid.details if trid else None,
            overall_status=combined["overall_status"].value if combined else None,
            can_proceed=combined["can_proceed"] if combined else None,
            checked_by=user.user_id,
        )

        # Audit
        audit_data = {
            "tool": "compliance_check",
            "regulation_type": regulation_type,
            "results": {k: v.status.value for k, v in results.items()},
        }
        if combined:
            audit_data["overall_status"] = combined["overall_status"].value
            audit_data["can_proceed"] = combined["can_proceed"]

        await write_audit_event(
            session,
            event_type="compliance_check",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data=audit_data,
        )
        await session.commit()

    # Format output
    lines = [f"Compliance Check -- Application #{application_id}", ""]

    for check_result in results.values():
        lines.append(f"{check_result.regulation}:")
        lines.extend(_format_check_result(check_result))
        lines.append("")

    if combined:
        lines.append(f"OVERALL STATUS: {combined['overall_status'].value}")
        can_proceed_text = "Yes" if combined["can_proceed"] else "No -- FAIL detected"
        lines.append(f"CAN PROCEED: {can_proceed_text}")
        lines.append("")

    lines.append(_DISCLAIMER)

    return "\n".join(lines)
