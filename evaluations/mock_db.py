# This project was developed with assistance from AI tools.
"""Mock database utilities for MLflow GenAI evaluation.

Provides mock session and data for evaluation without requiring a real database.
This allows agents to be evaluated on their behavior (response quality, tool routing,
persona adherence) without the complexity of database setup.

The mock data represents realistic but synthetic application/document/condition
scenarios that exercise the agent's tool-calling and response generation.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


# Mock application data
def mock_application(app_id: int = 667) -> SimpleNamespace:
    """Create a mock Application object."""
    return SimpleNamespace(
        id=app_id,
        stage="processing",
        loan_amount=Decimal("350000"),
        property_address="123 Main St, Springfield, IL 62701",
        loan_type="conventional_30",
        created_at=datetime.now() - timedelta(days=14),
        updated_at=datetime.now() - timedelta(days=1),
        borrower_id="eval-user-001",
        # Borrower info
        borrower_first_name="John",
        borrower_last_name="Doe",
        borrower_email="evaluator@example.com",
        # Financial info
        annual_income=Decimal("85000"),
        monthly_debts=Decimal("450"),
        down_payment=Decimal("70000"),
        credit_score=720,
    )


def mock_documents() -> list:
    """Create mock document list."""
    return [
        SimpleNamespace(
            id=1,
            type="w2",
            status="accepted",
            filename="w2_2024.pdf",
            uploaded_at=datetime.now() - timedelta(days=7),
        ),
        SimpleNamespace(
            id=2,
            type="pay_stub",
            status="pending_review",
            filename="paystub_march.pdf",
            uploaded_at=datetime.now() - timedelta(days=3),
        ),
        SimpleNamespace(
            id=3,
            type="bank_statement",
            status="uploaded",
            filename="bank_statement.pdf",
            uploaded_at=datetime.now() - timedelta(days=1),
        ),
    ]


def mock_conditions() -> list:
    """Create mock underwriting conditions."""
    return [
        SimpleNamespace(
            id=1,
            code="INC-001",
            description="Provide most recent pay stub dated within 30 days",
            severity="prior_to_approval",
            status="open",
            created_at=datetime.now() - timedelta(days=5),
        ),
        SimpleNamespace(
            id=2,
            code="VER-002",
            description="Verify employment with current employer",
            severity="prior_to_approval",
            status="responded",
            created_at=datetime.now() - timedelta(days=5),
        ),
    ]


def mock_rate_lock() -> SimpleNamespace:
    """Create mock rate lock status."""
    return SimpleNamespace(
        rate=Decimal("6.25"),
        lock_date=date.today() - timedelta(days=15),
        expiration_date=date.today() + timedelta(days=30),
        days_remaining=30,
        is_locked=True,
    )


def mock_disclosure_status() -> dict:
    """Create mock disclosure status."""
    return {
        "loan_estimate": {"status": "acknowledged", "acknowledged_at": datetime.now() - timedelta(days=10)},
        "closing_disclosure": {"status": "pending", "acknowledged_at": None},
        "trid_notice": {"status": "pending", "acknowledged_at": None},
    }


# Pipeline and analytics mocks for loan officer and CEO personas
def mock_pipeline_summary() -> dict:
    """Create mock pipeline summary for loan officer."""
    return {
        "total_applications": 24,
        "by_stage": {
            "inquiry": 3,
            "prequalification": 5,
            "application": 4,
            "processing": 6,
            "underwriting": 4,
            "conditional_approval": 2,
        },
        "avg_days_in_pipeline": 18,
    }


def mock_portfolio_analytics() -> dict:
    """Create mock portfolio analytics for CEO."""
    return {
        "total_volume": Decimal("45000000"),
        "total_loans": 127,
        "avg_loan_size": Decimal("354330"),
        "by_product_type": {
            "conventional_30": {"volume": Decimal("28000000"), "count": 82},
            "fha": {"volume": Decimal("12000000"), "count": 35},
            "va": {"volume": Decimal("5000000"), "count": 10},
        },
        "quarter": "Q1 2026",
    }


def mock_risk_exposure() -> dict:
    """Create mock risk exposure data."""
    return {
        "geographic_concentration": {
            "top_states": [
                {"state": "CA", "percentage": 28.5},
                {"state": "TX", "percentage": 18.2},
                {"state": "FL", "percentage": 12.1},
            ],
            "risk_level": "moderate",
        },
        "delinquency_rate": 1.8,
        "trend": "stable",
    }


class EvalSessionContext:
    """Context manager that patches SessionLocal for evaluation.

    Usage:
        with EvalSessionContext():
            result = await agent.ainvoke(state)
    """

    def __init__(self):
        self.patcher = None
        self.mock_session = None

    def __enter__(self):
        # Create mock session that returns mock data
        self.mock_session = AsyncMock()

        # Mock execute to return appropriate data based on query type
        mock_result = MagicMock()

        # Default returns for common query patterns
        mock_result.scalar.return_value = 1
        mock_result.unique.return_value.scalars.return_value.all.return_value = [mock_application()]
        mock_result.unique.return_value.scalar_one_or_none.return_value = mock_application()

        self.mock_session.execute = AsyncMock(return_value=mock_result)
        self.mock_session.add = MagicMock()
        self.mock_session.commit = AsyncMock()
        self.mock_session.flush = AsyncMock()
        self.mock_session.refresh = AsyncMock()

        # Create a context manager that yields the mock session
        async def mock_session_cm():
            yield self.mock_session

        # Patch SessionLocal in all tool modules
        self.patcher = patch(
            "db.database.SessionLocal",
            return_value=MagicMock(__aenter__=AsyncMock(return_value=self.mock_session),
                                    __aexit__=AsyncMock(return_value=None)),
        )
        self.patcher.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.patcher:
            self.patcher.stop()


def get_eval_session_patches() -> list:
    """Get list of patches for evaluation mode.

    Returns patch objects that mock database calls to return sample data.
    Caller is responsible for starting/stopping patches.
    """
    patches = []

    # Create a mock session factory
    def mock_session_factory():
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_result.unique.return_value.scalars.return_value.all.return_value = [mock_application()]
        mock_result.unique.return_value.scalar_one_or_none.return_value = mock_application()
        session.execute = AsyncMock(return_value=mock_result)

        # Return an async context manager
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    patches.append(
        patch("db.database.SessionLocal", side_effect=mock_session_factory)
    )

    return patches
