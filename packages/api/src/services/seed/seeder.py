# This project was developed with assistance from AI tools.
"""Demo data seeding service.

Seeds the database with realistic mortgage applications, borrowers,
documents, conditions, decisions, rate locks, and HMDA demographics
so all 5 personas have data to explore immediately after deployment.

Simulated for demonstration purposes -- not real financial data.
"""

import json
import logging
from datetime import UTC, datetime

from db import (
    Application,
    ApplicationBorrower,
    ApplicationFinancials,
    Borrower,
    Condition,
    Decision,
    DemoDataManifest,
    Document,
    DocumentExtraction,
    RateLock,
)
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import write_audit_event
from ..compliance.knowledge_base.ingestion import clear_kb_content, ingest_kb_content
from ..compliance.seed_hmda import clear_hmda_demographics, seed_hmda_demographics
from .fixtures import (
    ACTIVE_APPLICATIONS,
    BORROWERS,
    DAVID_PARK_ID,
    HISTORICAL_LOANS,
    HMDA_DEMOGRAPHICS,
    MARIA_CHEN_ID,
    compute_config_hash,
)

logger = logging.getLogger(__name__)


async def _check_manifest(session: AsyncSession) -> DemoDataManifest | None:
    """Check if demo data has been seeded."""
    result = await session.execute(
        select(DemoDataManifest).order_by(DemoDataManifest.id.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _clear_demo_data(session: AsyncSession, compliance_session: AsyncSession) -> None:
    """Delete all demo data by known borrower keycloak IDs."""
    known_ids = [b["keycloak_user_id"] for b in BORROWERS]

    # Find borrower rows to get their IDs for cascade
    result = await session.execute(
        select(Borrower.id).where(Borrower.keycloak_user_id.in_(known_ids))
    )
    borrower_ids = list(result.scalars().all())

    if borrower_ids:
        # Find application IDs via junction table
        app_result = await session.execute(
            select(ApplicationBorrower.application_id).where(
                ApplicationBorrower.borrower_id.in_(borrower_ids)
            )
        )
        app_ids = list(set(app_result.scalars().all()))

        if app_ids:
            # Delete child records first (no FK cascade assumed)
            doc_result = await session.execute(
                select(Document.id).where(Document.application_id.in_(app_ids))
            )
            doc_ids = list(doc_result.scalars().all())
            if doc_ids:
                await session.execute(
                    delete(DocumentExtraction).where(DocumentExtraction.document_id.in_(doc_ids))
                )
            await session.execute(delete(Document).where(Document.application_id.in_(app_ids)))
            await session.execute(delete(Condition).where(Condition.application_id.in_(app_ids)))
            await session.execute(delete(Decision).where(Decision.application_id.in_(app_ids)))
            await session.execute(delete(RateLock).where(RateLock.application_id.in_(app_ids)))
            await session.execute(
                delete(ApplicationFinancials).where(
                    ApplicationFinancials.application_id.in_(app_ids)
                )
            )
            # Truncate ALL audit events + violations to start clean hash chain.
            # TRUNCATE bypasses row triggers (no need to disable them).
            await session.execute(text("TRUNCATE TABLE audit_violations, audit_events CASCADE"))
            # Delete HMDA demographics via compliance module (isolation boundary)
            await clear_hmda_demographics(compliance_session, app_ids)
            # Delete junction rows
            await session.execute(
                delete(ApplicationBorrower).where(ApplicationBorrower.application_id.in_(app_ids))
            )
            # Delete applications
            await session.execute(delete(Application).where(Application.id.in_(app_ids)))

        # Delete borrowers
        await session.execute(delete(Borrower).where(Borrower.id.in_(borrower_ids)))

    # audit_events already truncated above; no per-type delete needed

    # Clear KB content
    await clear_kb_content(session)

    # Clear manifest
    await session.execute(delete(DemoDataManifest))

    logger.info("Cleared existing demo data")


def _create_borrower_map(borrowers: list[Borrower]) -> dict[str, int]:
    """Map keycloak_user_id -> borrower.id for FK resolution."""
    return {b.keycloak_user_id: b.id for b in borrowers}


async def _seed_applications(
    session: AsyncSession,
    app_defs: list[dict],
    borrower_map: dict[str, int],
) -> list[Application]:
    """Seed application records with financials, documents, conditions, decisions, rate locks."""
    applications = []

    for app_def in app_defs:
        borrower_id = borrower_map[app_def["borrower_ref"]]

        app = Application(
            stage=app_def["stage"],
            loan_type=app_def["loan_type"],
            property_address=app_def["property_address"],
            loan_amount=app_def["loan_amount"],
            property_value=app_def["property_value"],
            assigned_to=app_def["assigned_to"],
        )
        session.add(app)
        await session.flush()  # Get app.id

        # Create primary borrower junction row
        primary_junction = ApplicationBorrower(
            application_id=app.id,
            borrower_id=borrower_id,
            is_primary=True,
        )
        session.add(primary_junction)

        # Create co-borrower junction rows
        for co_ref in app_def.get("co_borrower_refs", []):
            co_borrower_id = borrower_map[co_ref]
            co_junction = ApplicationBorrower(
                application_id=app.id,
                borrower_id=co_borrower_id,
                is_primary=False,
            )
            session.add(co_junction)

        # Financials
        fin_data = app_def["financials"]
        financials = ApplicationFinancials(
            application_id=app.id,
            gross_monthly_income=fin_data["gross_monthly_income"],
            monthly_debts=fin_data["monthly_debts"],
            total_assets=fin_data["total_assets"],
            credit_score=fin_data["credit_score"],
            dti_ratio=fin_data["dti_ratio"],
        )
        session.add(financials)

        # Documents -- link to primary borrower
        for doc_def in app_def.get("documents", []):
            doc = Document(
                application_id=app.id,
                borrower_id=borrower_id,
                doc_type=doc_def["doc_type"],
                status=doc_def["status"],
                file_path=f"/demo/docs/{app.id}/{doc_def['doc_type'].value}.pdf",
                quality_flags=doc_def.get("quality_flags"),
                uploaded_by=app_def["borrower_ref"],
            )
            session.add(doc)
            await session.flush()

            # Seed extraction data for processed documents
            for ext_def in doc_def.get("extractions", []):
                extraction = DocumentExtraction(
                    document_id=doc.id,
                    field_name=ext_def["field_name"],
                    field_value=ext_def.get("field_value"),
                    confidence=ext_def.get("confidence"),
                    source_page=ext_def.get("source_page"),
                )
                session.add(extraction)

        # Conditions
        for cond_def in app_def.get("conditions", []):
            condition = Condition(
                application_id=app.id,
                description=cond_def["description"],
                severity=cond_def["severity"],
                status=cond_def["status"],
                issued_by=cond_def.get("issued_by"),
                cleared_by=cond_def.get("cleared_by"),
                due_date=cond_def.get("due_date"),
            )
            session.add(condition)

        # Decisions
        for dec_def in app_def.get("decisions", []):
            decision = Decision(
                application_id=app.id,
                decision_type=dec_def["decision_type"],
                rationale=dec_def["rationale"],
                decided_by=dec_def.get("decided_by"),
                denial_reasons=dec_def.get("denial_reasons"),
                created_at=dec_def.get("created_at"),
            )
            session.add(decision)

        # Rate lock
        if "rate_lock" in app_def:
            rl_def = app_def["rate_lock"]
            rate_lock = RateLock(
                application_id=app.id,
                locked_rate=rl_def["locked_rate"],
                lock_date=rl_def["lock_date"],
                expiration_date=rl_def["expiration_date"],
                is_active=rl_def["is_active"],
            )
            session.add(rate_lock)

        # Audit event for application creation (via write_audit_event for hash chain)
        await write_audit_event(
            session,
            event_type="application_created",
            user_id=app_def["assigned_to"],
            user_role="system",
            application_id=app.id,
            event_data={"source": "demo_seed", "stage": app_def["stage"].value},
        )

        applications.append(app)

    return applications


async def _seed_recent_audit_events(
    session: AsyncSession,
    active_apps: list[Application],
    app_defs: list[dict],
) -> None:
    """Create synthetic audit events simulating recent user activity.

    These become the most recent events in the audit trail, so the CEO
    dashboard "Recent Audit Events" card shows realistic actions instead
    of only "application created / system" rows.
    """
    # Map a few active apps to realistic recent events
    # Use first 3 active apps (they have different LOs assigned)
    events: list[dict] = [
        {
            "event_type": "stage_transition",
            "user_id": app_defs[0]["assigned_to"],
            "user_role": "loan_officer",
            "application_id": active_apps[0].id,
            "event_data": {
                "from_stage": "application",
                "to_stage": "underwriting",
                "reason": "All documentation received, submitting for review",
            },
        },
        {
            "event_type": "compliance_check",
            "user_id": MARIA_CHEN_ID,
            "user_role": "underwriter",
            "application_id": active_apps[2].id,
            "event_data": {
                "checks": ["ecoa", "atr_qm", "trid"],
                "result": "pass",
                "flags": 0,
            },
        },
        {
            "event_type": "credit_pull",
            "user_id": app_defs[1]["assigned_to"],
            "user_role": "loan_officer",
            "application_id": active_apps[1].id,
            "event_data": {
                "bureau": "equifax",
                "score": 742,
                "result": "approved",
            },
        },
        {
            "event_type": "condition_issued",
            "user_id": MARIA_CHEN_ID,
            "user_role": "underwriter",
            "application_id": active_apps[3].id,
            "event_data": {
                "condition_type": "prior_to_close",
                "title": "Updated pay stubs required",
            },
        },
        {
            "event_type": "decision",
            "user_id": MARIA_CHEN_ID,
            "user_role": "underwriter",
            "application_id": active_apps[4].id,
            "event_data": {
                "decision_type": "conditionally_approved",
                "rationale": "Strong financials, pending final documentation",
            },
        },
        {
            "event_type": "query",
            "user_id": DAVID_PARK_ID,
            "user_role": "ceo",
            "event_data": {
                "query_type": "pipeline_summary",
                "parameters": {"days": 90},
            },
        },
        {
            "event_type": "communication_sent",
            "user_id": app_defs[5]["assigned_to"],
            "user_role": "loan_officer",
            "application_id": active_apps[5].id,
            "event_data": {
                "channel": "email",
                "subject": "Application status update",
            },
        },
        {
            "event_type": "condition_cleared",
            "user_id": MARIA_CHEN_ID,
            "user_role": "underwriter",
            "application_id": active_apps[6].id,
            "event_data": {
                "condition_type": "prior_to_close",
                "title": "Proof of homeowners insurance",
            },
        },
    ]

    for evt in events:
        await write_audit_event(session, **evt)


async def seed_demo_data(
    session: AsyncSession,
    compliance_session: AsyncSession,
    force: bool = False,
) -> dict:
    """Seed demo data. Returns summary dict.

    Args:
        session: Main lending DB session.
        compliance_session: HMDA compliance DB session.
        force: If True, clear and re-seed even if already seeded.

    Returns:
        Summary dict with counts of seeded records.

    Raises:
        RuntimeError: If already seeded and force=False.
    """
    manifest = await _check_manifest(session)
    if manifest and not force:
        return {
            "status": "already_seeded",
            "seeded_at": manifest.seeded_at.isoformat(),
            "config_hash": manifest.config_hash,
        }

    if manifest and force:
        await _clear_demo_data(session, compliance_session)

    # 1. Create borrowers
    borrower_records = []
    for b_data in BORROWERS:
        borrower = Borrower(
            keycloak_user_id=b_data["keycloak_user_id"],
            first_name=b_data["first_name"],
            last_name=b_data["last_name"],
            email=b_data["email"],
            ssn=b_data.get("ssn"),
            dob=b_data.get("dob"),
        )
        session.add(borrower)
        borrower_records.append(borrower)

    await session.flush()  # Get borrower IDs
    borrower_map = _create_borrower_map(borrower_records)

    # 2. Seed active applications
    active_apps = await _seed_applications(session, ACTIVE_APPLICATIONS, borrower_map)

    # 3. Seed historical loans
    historical_apps = await _seed_applications(session, HISTORICAL_LOANS, borrower_map)

    all_apps = active_apps + historical_apps

    # 4. Seed HMDA demographics via compliance session
    hmda_records = []
    for i, demo_data in enumerate(HMDA_DEMOGRAPHICS):
        if i < len(all_apps):
            app_def = (ACTIVE_APPLICATIONS + HISTORICAL_LOANS)[i]
            primary_borrower_id = borrower_map.get(app_def["borrower_ref"])
            hmda_records.append(
                {
                    "application_id": all_apps[i].id,
                    "borrower_id": primary_borrower_id,
                    "race": demo_data["race"],
                    "ethnicity": demo_data["ethnicity"],
                    "sex": demo_data["sex"],
                    "age": demo_data.get("age"),
                    "collection_method": demo_data["collection_method"],
                }
            )

    hmda_count = await seed_hmda_demographics(compliance_session, hmda_records)

    # 5. Ingest compliance KB content
    kb_summary = await ingest_kb_content(session)

    # 6. Write manifest
    config_hash = compute_config_hash()
    summary = {
        "borrowers": len(borrower_records),
        "active_applications": len(active_apps),
        "historical_loans": len(historical_apps),
        "hmda_demographics": hmda_count,
        "kb_documents": kb_summary["documents"],
        "kb_chunks": kb_summary["chunks"],
    }

    manifest = DemoDataManifest(
        config_hash=config_hash,
        summary=json.dumps(summary),
    )
    session.add(manifest)

    # Seed-level audit event (via write_audit_event for hash chain)
    await write_audit_event(
        session,
        event_type="demo_data_seeded",
        user_id="system",
        user_role="system",
        event_data=summary,
    )

    # 7. Synthetic audit events simulating recent user activity.
    # Written last so they get the highest IDs and appear as "most recent"
    # in the CEO dashboard audit events card.
    await _seed_recent_audit_events(session, active_apps, ACTIVE_APPLICATIONS)

    # Collect timestamp overrides before commit (ORM objects expire after commit)
    all_defs = ACTIVE_APPLICATIONS + HISTORICAL_LOANS
    ts_overrides = []
    for app, app_def in zip(all_apps, all_defs):
        if "created_at" in app_def or "updated_at" in app_def:
            created = app_def.get("created_at")
            updated = app_def.get("updated_at") or created
            ts_overrides.append({"id": app.id, "c": created, "u": updated})

    # 7. Commit both sessions.
    # NOTE: These are separate DB connections so this is NOT atomic. If the
    # compliance commit fails after the lending commit succeeds, the manifest
    # will record "seeded" but HMDA data will be missing. In that case,
    # re-run with --force to clear and re-seed.
    await session.commit()

    # Apply timestamp overrides via engine connection to bypass ORM entirely
    if ts_overrides:
        from db.database import engine

        async with engine.begin() as conn:
            for ts in ts_overrides:
                await conn.execute(
                    text("UPDATE applications SET created_at = :c, updated_at = :u WHERE id = :id"),
                    ts,
                )

    try:
        await compliance_session.commit()
    except Exception:
        logger.error(
            "Compliance session commit failed after lending commit succeeded. "
            "HMDA demographics may be missing. Re-run with --force to fix."
        )
        raise

    logger.info("Demo data seeded: %s", summary)

    return {
        "status": "seeded",
        "seeded_at": datetime.now(UTC).isoformat(),
        "config_hash": config_hash,
        **summary,
    }


async def get_seed_status(session: AsyncSession) -> dict:
    """Check if demo data has been seeded."""
    manifest = await _check_manifest(session)
    if manifest is None:
        return {"seeded": False}
    return {
        "seeded": True,
        "seeded_at": manifest.seeded_at.isoformat(),
        "config_hash": manifest.config_hash,
        "summary": json.loads(manifest.summary) if manifest.summary else None,
    }
