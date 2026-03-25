# This project was developed with assistance from AI tools.
"""Fixtures for functional tests.

The real app from ``src.main`` is a module singleton. ``_clean_overrides``
ensures dependency_overrides are cleared after every test so persona
configuration from one test never leaks into the next.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app as real_app
from src.schemas.auth import UserContext

from .mock_db import configure_app_for_persona


@pytest.fixture(autouse=True)
def _clean_overrides():
    """Clear app dependency overrides after each test."""
    yield
    real_app.dependency_overrides.clear()


@pytest.fixture
def app():
    """Return the real FastAPI app with all routers mounted."""
    return real_app


@pytest.fixture
def make_client(app):
    """Factory fixture: configure persona + mock DB, return TestClient."""

    def _make(user: UserContext, session: AsyncMock) -> TestClient:
        configure_app_for_persona(app, user, session)
        return TestClient(app)

    return _make


@pytest.fixture
def make_upload_client(app):
    """Factory fixture: configure persona + mock DB + mock storage + mock extraction.

    Returns (TestClient, mock_storage). The storage and extraction patches
    are automatically stopped after each test.

    Background extraction dispatch (asyncio.create_task) is suppressed so
    upload tests can focus on the upload path itself. Extraction pipeline
    coverage lives in test_extraction.py (unit tests that call
    process_document directly).
    """
    patchers = []

    def _make(user: UserContext, session: AsyncMock) -> tuple[TestClient, MagicMock]:
        configure_app_for_persona(app, user, session)

        mock_storage = MagicMock()
        mock_storage.build_object_key.return_value = "101/501/test.pdf"
        mock_storage.upload_file = AsyncMock(return_value="101/501/test.pdf")

        patcher_storage = patch(
            "src.services.document.get_storage_service", return_value=mock_storage
        )
        patcher_storage.start()
        patchers.append(patcher_storage)

        # Mock extraction service so background task dispatch doesn't fail
        mock_extraction_svc = MagicMock()
        mock_extraction_svc.process_document = AsyncMock()
        patcher_extraction = patch(
            "src.routes.documents.get_extraction_service",
            return_value=mock_extraction_svc,
        )
        patcher_extraction.start()
        patchers.append(patcher_extraction)

        # Mock audit so upload tests don't need a full audit chain
        patcher_audit = patch("src.services.document.write_audit_event", new_callable=AsyncMock)
        patcher_audit.start()
        patchers.append(patcher_audit)

        # Only mock create_task, not the entire asyncio module
        patcher_create_task = patch(
            "src.routes.documents.asyncio.create_task", new_callable=MagicMock
        )
        mock_create_task = patcher_create_task.start()
        patchers.append(patcher_create_task)

        client = TestClient(app)
        client._mock_storage = mock_storage
        client._mock_extraction_svc = mock_extraction_svc
        client._mock_create_task = mock_create_task
        return client, mock_storage

    yield _make

    for p in patchers:
        p.stop()
