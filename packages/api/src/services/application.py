# This project was developed with assistance from AI tools.
"""Application service with role-based data scope filtering.

Every query is filtered through the caller's DataScope so that borrowers
see only their own applications, loan officers see only assigned ones,
and CEO/underwriter/admin see all.
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from db import Application, ApplicationBorrower, ApplicationFinancials, Borrower
from db.enums import ApplicationStage, LoanType
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..schemas.auth import UserContext
from ..services.scope import apply_data_scope

logger = logging.getLogger(__name__)


class InvalidTransitionError(ValueError):
    """Raised when an application stage transition is not allowed."""

    pass


_TERMINAL_STAGES = ApplicationStage.terminal_stages()

_SORT_COLUMNS = {
    "updated_at": Application.updated_at.desc(),
    "loan_amount": Application.loan_amount.desc().nulls_last(),
}


async def list_applications(
    session: AsyncSession,
    user: UserContext,
    *,
    offset: int = 0,
    limit: int = 20,
    filter_stage: ApplicationStage | None = None,
    filter_stalled: bool = False,
    sort_by: str | None = None,
) -> tuple[list[Application], int]:
    """Return applications visible to the current user.

    Args:
        filter_stage: Only return applications in this stage.
        filter_stalled: Only return non-terminal apps with no activity for 7+ days.
        sort_by: Sort key -- "updated_at", "loan_amount", or "urgency".
            "urgency" is handled post-query by the route layer.
    """
    # Count query -- use DISTINCT to prevent inflation from junction join
    count_stmt = select(func.count(func.distinct(Application.id)))
    count_stmt = apply_data_scope(count_stmt, user.data_scope, user)
    count_stmt = _apply_filters(count_stmt, filter_stage, filter_stalled)
    total = (await session.execute(count_stmt)).scalar() or 0

    # Data query
    order = _SORT_COLUMNS.get(sort_by, Application.updated_at.desc())
    stmt = (
        select(Application)
        .options(
            selectinload(Application.application_borrowers).joinedload(
                ApplicationBorrower.borrower
            ),
            selectinload(Application.prequalification_decision),
        )
        .order_by(order)
        .offset(offset)
        .limit(limit)
    )
    stmt = apply_data_scope(stmt, user.data_scope, user)
    stmt = _apply_filters(stmt, filter_stage, filter_stalled)
    result = await session.execute(stmt)
    applications = result.unique().scalars().all()

    return applications, total


def _apply_filters(stmt, filter_stage, filter_stalled):
    """Apply optional WHERE clauses for stage and stalled filters."""
    if filter_stage is not None:
        stmt = stmt.where(Application.stage == filter_stage)
    if filter_stalled:
        cutoff = datetime.now(UTC) - timedelta(days=7)
        stmt = stmt.where(
            Application.updated_at < cutoff,
            Application.stage.notin_([s.value for s in _TERMINAL_STAGES]),
        )
    return stmt


async def get_application(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
) -> Application | None:
    """Return a single application if visible to the current user.

    Returns None (which the route maps to 404) for out-of-scope applications
    rather than 403, to avoid leaking existence of resources.
    """
    stmt = (
        select(Application)
        .options(
            selectinload(Application.application_borrowers).joinedload(
                ApplicationBorrower.borrower
            ),
            selectinload(Application.prequalification_decision),
        )
        .where(Application.id == application_id)
    )
    stmt = apply_data_scope(stmt, user.data_scope, user)
    result = await session.execute(stmt)
    return result.unique().scalar_one_or_none()


async def create_application(
    session: AsyncSession,
    user: UserContext,
    loan_type: LoanType | None = None,
    property_address: str | None = None,
    loan_amount: Decimal | None = None,
    property_value: Decimal | None = None,
) -> Application:
    """Create a new application for the current borrower."""
    # Find or create borrower record for the authenticated user
    stmt = select(Borrower).where(Borrower.keycloak_user_id == user.user_id)
    result = await session.execute(stmt)
    borrower = result.scalar_one_or_none()

    if borrower is None:
        borrower = Borrower(
            keycloak_user_id=user.user_id,
            first_name=user.name.split()[0] if user.name else "Unknown",
            last_name=user.name.split()[-1] if user.name and len(user.name.split()) > 1 else "",
            email=user.email,
        )
        session.add(borrower)
        await session.flush()

    application = Application(
        loan_type=loan_type,
        property_address=property_address,
        loan_amount=loan_amount,
        property_value=property_value,
    )
    session.add(application)
    await session.flush()

    # Create junction row linking borrower as primary
    junction = ApplicationBorrower(
        application_id=application.id,
        borrower_id=borrower.id,
        is_primary=True,
    )
    session.add(junction)
    app_id = application.id  # capture before commit expires the object
    await session.commit()
    # Re-query with eager loading to avoid lazy-load in async context
    return await get_application(session, user, app_id)


_UPDATABLE_FIELDS = {
    "loan_type",
    "property_address",
    "loan_amount",
    "property_value",
    "assigned_to",
}


async def transition_stage(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    new_stage: ApplicationStage,
) -> Application | None:
    """Transition an application to a new stage with validation.

    Returns None if the application is not found or not accessible.
    Raises InvalidTransitionError if the transition is not allowed.
    """
    app = await get_application(session, user, application_id)
    if app is None:
        return None

    current = app.stage or ApplicationStage.INQUIRY
    valid = ApplicationStage.valid_transitions()
    allowed = valid.get(current, frozenset())

    if new_stage not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition from '{current.value}' to '{new_stage.value}'. "
            f"Allowed: {sorted(s.value for s in allowed) if allowed else 'none (terminal stage)'}."
        )

    app.stage = new_stage
    await session.commit()
    return await get_application(session, user, application_id)


async def update_application(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    **updates,
) -> Application | None:
    """Update an application if visible to the current user.

    Stage transitions must use ``transition_stage()`` instead.
    Passing 'stage' in updates is silently ignored.
    """
    app = await get_application(session, user, application_id)
    if app is None:
        return None

    for field, value in updates.items():
        if field not in _UPDATABLE_FIELDS:
            continue
        setattr(app, field, value)

    await session.commit()
    # Re-query with eager loading to avoid lazy-load in async context
    return await get_application(session, user, application_id)


async def get_financials(
    session: AsyncSession,
    application_id: int,
) -> list[ApplicationFinancials]:
    """Get all financial records for an application.

    Does NOT enforce data scope -- caller must check access to the application first.

    Args:
        session: Database session.
        application_id: The application ID.

    Returns:
        List of ApplicationFinancials objects (may be empty).
    """
    stmt = select(ApplicationFinancials).where(
        ApplicationFinancials.application_id == application_id
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def add_borrower(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    borrower_id: int,
    is_primary: bool,
) -> Application | None:
    """Add a borrower to an application.

    Args:
        session: Database session.
        user: Current user context.
        application_id: The application ID.
        borrower_id: The borrower ID to add.
        is_primary: Whether this borrower should be primary.

    Returns:
        Updated Application with borrowers loaded, or None if not found.

    Raises:
        ValueError: If borrower doesn't exist or is already linked.
    """
    from . import audit

    # Verify application exists and is accessible
    app = await get_application(session, user, application_id)
    if app is None:
        return None

    # Verify borrower exists
    borrower_result = await session.execute(select(Borrower).where(Borrower.id == borrower_id))
    if borrower_result.scalar_one_or_none() is None:
        raise ValueError("Borrower not found")

    # Check for duplicate junction row
    dup_result = await session.execute(
        select(ApplicationBorrower).where(
            ApplicationBorrower.application_id == application_id,
            ApplicationBorrower.borrower_id == borrower_id,
        )
    )
    if dup_result.scalar_one_or_none() is not None:
        raise ValueError("Borrower already linked to this application")

    # Create junction row and write audit event in a single commit
    junction = ApplicationBorrower(
        application_id=application_id,
        borrower_id=borrower_id,
        is_primary=is_primary,
    )
    session.add(junction)

    await audit.write_audit_event(
        session,
        event_type="co_borrower_added",
        user_id=user.user_id,
        user_role=user.role.value,
        application_id=application_id,
        event_data={"borrower_id": borrower_id, "is_primary": is_primary},
    )
    await session.commit()

    # Return refreshed application
    return await get_application(session, user, application_id)


async def remove_borrower(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    borrower_id: int,
) -> Application | None:
    """Remove a borrower from an application.

    Args:
        session: Database session.
        user: Current user context.
        application_id: The application ID.
        borrower_id: The borrower ID to remove.

    Returns:
        Updated Application with borrowers loaded, or None if not found.

    Raises:
        ValueError: If borrower is not linked, is primary, or is the last borrower.
    """
    from . import audit

    # Verify application exists and is accessible
    app = await get_application(session, user, application_id)
    if app is None:
        return None

    # Find the junction row
    junction_result = await session.execute(
        select(ApplicationBorrower).where(
            ApplicationBorrower.application_id == application_id,
            ApplicationBorrower.borrower_id == borrower_id,
        )
    )
    junction = junction_result.scalar_one_or_none()
    if junction is None:
        raise ValueError("Borrower not linked to this application")

    # Count remaining borrowers (must keep at least one)
    count_result = await session.execute(
        select(func.count()).where(ApplicationBorrower.application_id == application_id)
    )
    if count_result.scalar() <= 1:
        raise ValueError("Cannot remove the last borrower from an application")

    # Cannot remove primary without reassigning first
    if junction.is_primary:
        raise ValueError("Cannot remove the primary borrower. Reassign primary first.")

    # Delete junction row and write audit event in a single commit
    await session.delete(junction)

    await audit.write_audit_event(
        session,
        event_type="co_borrower_removed",
        user_id=user.user_id,
        user_role=user.role.value,
        application_id=application_id,
        event_data={"borrower_id": borrower_id},
    )
    await session.commit()

    # Return refreshed application
    return await get_application(session, user, application_id)
