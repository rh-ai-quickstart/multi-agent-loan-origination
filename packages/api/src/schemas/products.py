# This project was developed with assistance from AI tools.
"""Product information schemas."""

from pydantic import BaseModel


class ProductEligibility(BaseModel):
    """Eligibility criteria for a mortgage product."""

    min_credit_score: int
    max_dti_pct: float
    max_ltv_pct: float
    special_requirements: str | None = None


class ProductInfo(BaseModel):
    """Mortgage product information for public display."""

    id: str
    name: str
    description: str
    min_down_payment_pct: float
    typical_rate: float
    eligibility: ProductEligibility
