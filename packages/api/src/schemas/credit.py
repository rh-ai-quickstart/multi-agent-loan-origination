# This project was developed with assistance from AI tools.
"""Credit bureau pull result schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SoftPullResult(BaseModel):
    """Result from a soft credit bureau pull."""

    credit_score: int = Field(..., ge=300, le=850)
    bureau: str = "mock_equifax"
    outstanding_accounts: int = 0
    total_outstanding_debt: Decimal = Decimal("0.00")
    derogatory_marks: int = 0
    oldest_account_years: int = 0


class TradeLineDetail(BaseModel):
    """Individual trade line from a hard pull."""

    account_type: str
    balance: Decimal
    credit_limit: Decimal | None = None
    monthly_payment: Decimal
    status: str  # "current", "late_30", "late_60", "late_90", "collection"
    opened_years_ago: int


class HardPullResult(SoftPullResult):
    """Result from a hard credit bureau pull (extends soft pull)."""

    trade_lines: list[TradeLineDetail] = Field(default_factory=list)
    collections_count: int = 0
    bankruptcy_flag: bool = False
    public_records_count: int = 0


class CreditReportResponse(BaseModel):
    """API response for a credit report."""

    id: int
    borrower_id: int
    application_id: int
    pull_type: str
    credit_score: int
    bureau: str
    outstanding_accounts: int | None
    total_outstanding_debt: Decimal | None
    derogatory_marks: int | None
    oldest_account_years: int | None
    pulled_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}
