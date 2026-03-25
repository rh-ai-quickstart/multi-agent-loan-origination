# This project was developed with assistance from AI tools.
"""Unit tests for LO-specific service functions.

Tests: update_document_status (document service) and
check_underwriting_readiness (completeness service).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db.enums import ApplicationStage, DocumentStatus, DocumentType

from src.schemas.auth import DataScope, UserContext
from src.schemas.completeness import CompletenessResponse, DocumentRequirement
from src.services.completeness import check_underwriting_readiness
from src.services.document import update_document_status

# Shared LO user context
_LO_USER = UserContext(
    user_id="lo-test",
    role="loan_officer",
    email="lo@test.com",
    name="Test LO",
    data_scope=DataScope(assigned_to="lo-test"),
)


# ---------------------------------------------------------------------------
# update_document_status
# ---------------------------------------------------------------------------


class TestUpdateDocumentStatus:
    """Tests for update_document_status service function."""

    @pytest.mark.asyncio
    async def test_flag_resubmission_from_processing_complete(self):
        """Happy path: flag a PROCESSING_COMPLETE doc for resubmission."""
        mock_doc = MagicMock()
        mock_doc.id = 10
        mock_doc.application_id = 101
        mock_doc.status = DocumentStatus.PROCESSING_COMPLETE
        mock_doc.quality_flags = None

        session = AsyncMock()

        with (
            patch(
                "src.services.document.get_document",
                new_callable=AsyncMock,
                return_value=mock_doc,
            ),
            patch(
                "src.services.document.write_audit_event",
                new_callable=AsyncMock,
            ),
        ):
            result = await update_document_status(
                session,
                _LO_USER,
                application_id=101,
                document_id=10,
                new_status=DocumentStatus.FLAGGED_FOR_RESUBMISSION,
                reason="Illegible scan",
            )

        assert result is not None
        assert mock_doc.status == DocumentStatus.FLAGGED_FOR_RESUBMISSION
        assert mock_doc.quality_flags == "Illegible scan"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_flag_from_uploaded_status(self):
        """Cannot flag an UPLOADED doc -- it hasn't been processed yet."""
        mock_doc = MagicMock()
        mock_doc.id = 10
        mock_doc.application_id = 101
        mock_doc.status = DocumentStatus.UPLOADED

        session = AsyncMock()

        with (
            patch(
                "src.services.document.get_document",
                new_callable=AsyncMock,
                return_value=mock_doc,
            ),
            pytest.raises(ValueError, match="Cannot flag document"),
        ):
            await update_document_status(
                session,
                _LO_USER,
                application_id=101,
                document_id=10,
                new_status=DocumentStatus.FLAGGED_FOR_RESUBMISSION,
            )

    @pytest.mark.asyncio
    async def test_rejects_mismatched_application_id(self):
        """Prevents cross-application document manipulation."""
        mock_doc = MagicMock()
        mock_doc.id = 10
        mock_doc.application_id = 999  # Different from requested

        session = AsyncMock()

        with patch(
            "src.services.document.get_document",
            new_callable=AsyncMock,
            return_value=mock_doc,
        ):
            result = await update_document_status(
                session,
                _LO_USER,
                application_id=101,
                document_id=10,
                new_status=DocumentStatus.FLAGGED_FOR_RESUBMISSION,
            )

        assert result is None


# ---------------------------------------------------------------------------
# check_underwriting_readiness
# ---------------------------------------------------------------------------


def _make_completeness(
    *,
    is_complete: bool = True,
    requirements: list[DocumentRequirement] | None = None,
) -> CompletenessResponse:
    """Build a CompletenessResponse for testing."""
    if requirements is None:
        requirements = [
            DocumentRequirement(
                doc_type=DocumentType.W2,
                label="W-2 Form",
                is_provided=True,
                document_id=1,
                status=DocumentStatus.PROCESSING_COMPLETE,
            ),
            DocumentRequirement(
                doc_type=DocumentType.BANK_STATEMENT,
                label="Bank Statement",
                is_provided=True,
                document_id=2,
                status=DocumentStatus.PROCESSING_COMPLETE,
            ),
        ]
    provided = sum(1 for r in requirements if r.is_provided)
    return CompletenessResponse(
        application_id=101,
        is_complete=is_complete,
        requirements=requirements,
        provided_count=provided,
        required_count=len(requirements),
    )


class TestCheckUnderwritingReadiness:
    """Tests for check_underwriting_readiness service function."""

    @pytest.mark.asyncio
    async def test_ready_when_all_criteria_met(self):
        """Returns is_ready=True when stage, docs, and quality all pass."""
        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.APPLICATION

        session = AsyncMock()

        with (
            patch(
                "src.services.completeness.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.services.completeness.check_completeness",
                new_callable=AsyncMock,
                return_value=_make_completeness(),
            ),
        ):
            result = await check_underwriting_readiness(session, _LO_USER, 101)

        assert result is not None
        assert result["is_ready"] is True
        assert result["blockers"] == []

    @pytest.mark.asyncio
    async def test_multiple_blockers_accumulated(self):
        """When docs are missing AND still processing, both blockers appear."""
        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.APPLICATION

        reqs = [
            DocumentRequirement(
                doc_type=DocumentType.W2,
                label="W-2 Form",
                is_provided=False,
            ),
            DocumentRequirement(
                doc_type=DocumentType.BANK_STATEMENT,
                label="Bank Statement",
                is_provided=True,
                document_id=2,
                status=DocumentStatus.UPLOADED,
            ),
        ]
        completeness = _make_completeness(is_complete=False, requirements=reqs)

        session = AsyncMock()

        with (
            patch(
                "src.services.completeness.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.services.completeness.check_completeness",
                new_callable=AsyncMock,
                return_value=completeness,
            ),
        ):
            result = await check_underwriting_readiness(session, _LO_USER, 101)

        assert result["is_ready"] is False
        assert len(result["blockers"]) == 2
        assert any("Missing" in b for b in result["blockers"])
        assert any("processing" in b.lower() for b in result["blockers"])

    @pytest.mark.asyncio
    async def test_wrong_stage_blocks_submission(self):
        """Stage guard blocks even when everything else is fine."""
        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING

        session = AsyncMock()

        with (
            patch(
                "src.services.completeness.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.services.completeness.check_completeness",
                new_callable=AsyncMock,
                return_value=_make_completeness(),
            ),
        ):
            result = await check_underwriting_readiness(session, _LO_USER, 101)

        assert result["is_ready"] is False
        assert any("underwriting" in b for b in result["blockers"])
