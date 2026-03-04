# This project was developed with assistance from AI tools.
"""Tests for bureau_credit_score override in compute_risk_factors."""

from unittest.mock import MagicMock

from src.agents.risk_tools import compute_risk_factors


def _make_fin(*, credit_score=720, income=8000, debts=1200, assets=60000):
    fin = MagicMock()
    fin.credit_score = credit_score
    fin.gross_monthly_income = income
    fin.monthly_debts = debts
    fin.total_assets = assets
    return fin


def _make_app(*, loan_amount=350000, property_value=450000):
    app = MagicMock()
    app.loan_amount = loan_amount
    app.property_value = property_value
    return app


class TestBureauCreditScoreOverride:
    """Tests for the bureau_credit_score keyword argument."""

    def test_uses_self_reported_when_no_bureau(self):
        """Without bureau score, self-reported credit score is used."""
        fin = _make_fin(credit_score=720)
        risk = compute_risk_factors(_make_app(), [fin], [])
        assert risk.credit["value"] == 720

    def test_bureau_overrides_self_reported(self):
        """Bureau score takes precedence over self-reported."""
        fin = _make_fin(credit_score=720)
        risk = compute_risk_factors(_make_app(), [fin], [], bureau_credit_score=680)
        # Bureau score 680 used instead of self-reported 720
        assert risk.credit["value"] == 680
        assert risk.credit["rating"] == "Medium"

    def test_bureau_changes_risk_rating(self):
        """Bureau score of 610 produces High risk despite self-reported 750."""
        fin = _make_fin(credit_score=750)
        risk_without = compute_risk_factors(_make_app(), [fin], [])
        risk_with = compute_risk_factors(_make_app(), [fin], [], bureau_credit_score=610)
        assert risk_without.credit["rating"] == "Low"
        # 610 < 620 threshold -> High risk
        assert risk_with.credit["rating"] == "High"
        assert risk_with.credit["value"] == 610

    def test_bureau_none_falls_through_to_self_reported(self):
        """Explicitly passing None uses self-reported."""
        fin = _make_fin(credit_score=700)
        risk = compute_risk_factors(_make_app(), [fin], [], bureau_credit_score=None)
        assert risk.credit["value"] == 700

    def test_bureau_with_no_self_reported(self):
        """Bureau score used even when no self-reported score exists."""
        fin = _make_fin(credit_score=None)
        risk = compute_risk_factors(_make_app(), [fin], [], bureau_credit_score=740)
        assert risk.credit["value"] == 740
        assert risk.credit["rating"] == "Low"

    def test_no_bureau_no_self_reported_warns(self):
        """No scores at all produces warning."""
        fin = _make_fin(credit_score=None)
        risk = compute_risk_factors(_make_app(), [fin], [])
        assert risk.credit["value"] is None
        assert "No credit score on file" in risk.warnings
