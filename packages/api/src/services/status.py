# This project was developed with assistance from AI tools.
"""Application status aggregation service.

Combines stage info, document completeness, and open conditions into a
single status summary for the borrower or loan officer.
"""

import logging

from db import Application, Condition
from db.enums import ApplicationStage, ConditionStatus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.auth import UserContext
from ..schemas.status import (
    ApplicationStatusResponse,
    PendingAction,
    StageInfo,
)
from ..services.application import get_application
from ..services.completeness import check_completeness

logger = logging.getLogger(__name__)

# Human-readable descriptions for each application stage.
STAGE_INFO: dict[str, StageInfo] = {
    ApplicationStage.INQUIRY.value: StageInfo(
        label="Inquiry",
        description="Your inquiry has been received. A loan officer will reach out soon.",
        next_step="Complete your loan application to move forward.",
        typical_timeline="1-2 business days",
    ),
    ApplicationStage.PREQUALIFICATION.value: StageInfo(
        label="Pre-Qualification",
        description="We're reviewing your basic financial information for a preliminary assessment.",
        next_step="You'll receive a pre-qualification letter if eligible.",
        typical_timeline="1-3 business days",
    ),
    ApplicationStage.APPLICATION.value: StageInfo(
        label="Application",
        description="Your formal loan application is in progress. Upload required documents to proceed.",
        next_step="Submit all required documents so we can begin processing.",
        typical_timeline="Depends on document submission",
    ),
    ApplicationStage.PROCESSING.value: StageInfo(
        label="Processing",
        description="Your loan officer is verifying your information and ordering third-party reports.",
        next_step="The file will be sent to underwriting once processing is complete.",
        typical_timeline="1-2 weeks",
    ),
    ApplicationStage.UNDERWRITING.value: StageInfo(
        label="Underwriting",
        description="An underwriter is evaluating your application against lending guidelines.",
        next_step="You may receive conditions to satisfy before a decision is issued.",
        typical_timeline="1-2 weeks",
    ),
    ApplicationStage.CONDITIONAL_APPROVAL.value: StageInfo(
        label="Conditional Approval",
        description="Your loan is conditionally approved. Outstanding conditions must be cleared.",
        next_step="Submit documents or information to satisfy the listed conditions.",
        typical_timeline="Varies by condition complexity",
    ),
    ApplicationStage.CLEAR_TO_CLOSE.value: StageInfo(
        label="Clear to Close",
        description="All conditions are satisfied. Your loan is approved and ready for closing.",
        next_step="Review and sign your closing documents.",
        typical_timeline="3-5 business days to closing",
    ),
    ApplicationStage.CLOSED.value: StageInfo(
        label="Closed",
        description="Your loan has been funded and closed. Congratulations!",
        next_step="No further action required.",
        typical_timeline="Complete",
    ),
    ApplicationStage.DENIED.value: StageInfo(
        label="Denied",
        description="Your loan application was not approved at this time.",
        next_step="You will receive a written notice explaining the reasons.",
        typical_timeline="Complete",
    ),
    ApplicationStage.WITHDRAWN.value: StageInfo(
        label="Withdrawn",
        description="This application has been withdrawn.",
        next_step="No further action required. You may start a new application at any time.",
        typical_timeline="Complete",
    ),
}

_TERMINAL_STAGES = ApplicationStage.terminal_stages()

_RESOLVED_CONDITION_STATUSES = {
    ConditionStatus.CLEARED,
    ConditionStatus.WAIVED,
}


async def get_application_status(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    *,
    return_app: bool = False,
) -> ApplicationStatusResponse | None | tuple["ApplicationStatusResponse", "Application"]:
    """Build an aggregated status summary for an application.

    Returns None if the application is not found or not accessible.
    If return_app=True, returns (response, app) tuple to avoid redundant queries.
    """
    # Get document completeness (also validates app exists + scope)
    completeness = await check_completeness(session, user, application_id)
    if completeness is None:
        return None

    # check_completeness already validated access; load app for stage info
    app = await get_application(session, user, application_id)
    stage = app.stage.value if app.stage else ApplicationStage.INQUIRY.value

    stage_info = STAGE_INFO.get(
        stage,
        StageInfo(
            label=stage.replace("_", " ").title(),
            description="Your application is being processed.",
            next_step="Contact your loan officer for details.",
            typical_timeline="Varies",
        ),
    )

    # Count open conditions
    open_conditions_count = 0
    if stage not in _TERMINAL_STAGES:
        result = await session.execute(
            select(func.count())
            .select_from(Condition)
            .where(
                Condition.application_id == application_id,
                Condition.status.notin_([s for s in _RESOLVED_CONDITION_STATUSES]),
            )
        )
        open_conditions_count = result.scalar() or 0

    # Build pending actions
    pending_actions: list[PendingAction] = []
    if stage not in _TERMINAL_STAGES:
        # Missing documents
        missing_docs = [r for r in completeness.requirements if not r.is_provided]
        for req in missing_docs:
            pending_actions.append(
                PendingAction(
                    action_type="upload_document",
                    description=f"Upload {req.label}",
                )
            )

        # Quality issues on provided documents
        for req in completeness.requirements:
            if req.is_provided and req.quality_flags:
                flags = ", ".join(req.quality_flags)
                pending_actions.append(
                    PendingAction(
                        action_type="resubmit_document",
                        description=f"Resubmit {req.label} ({flags})",
                    )
                )

        # Open conditions
        if open_conditions_count > 0:
            pending_actions.append(
                PendingAction(
                    action_type="clear_conditions",
                    description=f"{open_conditions_count} underwriting condition(s) to resolve",
                )
            )

    response = ApplicationStatusResponse(
        application_id=application_id,
        stage=stage,
        stage_info=stage_info,
        is_document_complete=completeness.is_complete,
        provided_doc_count=completeness.provided_count,
        required_doc_count=completeness.required_count,
        open_condition_count=open_conditions_count,
        pending_actions=pending_actions,
    )
    if return_app:
        return response, app
    return response
