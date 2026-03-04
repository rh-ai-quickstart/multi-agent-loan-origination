# This project was developed with assistance from AI tools.
"""Tests for mock credit bureau service."""

from decimal import Decimal

from src.services.credit_bureau import CreditBureauService
from src.services.seed.fixtures import (
    DANIEL_RAMIREZ_ID,
    SARAH_MITCHELL_ID,
    THOMAS_NGUYEN_ID,
)


def _service():
    return CreditBureauService()


class TestSoftPull:
    """Soft credit pull tests."""

    def test_should_return_seed_profile_for_known_user(self):
        result = _service().soft_pull(borrower_id=1, keycloak_user_id=SARAH_MITCHELL_ID)

        assert result.credit_score == 742
        assert result.bureau == "mock_equifax"
        assert result.outstanding_accounts == 4
        assert result.total_outstanding_debt == Decimal("45200.00")
        assert result.derogatory_marks == 0
        assert result.oldest_account_years == 12

    def test_should_return_seed_profile_for_low_credit_borrower(self):
        """Low-credit seed profiles matter for denial/condition flows downstream."""
        result = _service().soft_pull(borrower_id=1, keycloak_user_id=DANIEL_RAMIREZ_ID)

        assert result.credit_score == 612
        assert result.derogatory_marks == 3
        assert result.outstanding_accounts == 8

    def test_should_generate_deterministic_profile_from_borrower_id(self):
        svc = _service()
        result1 = svc.soft_pull(borrower_id=99)
        result2 = svc.soft_pull(borrower_id=99)

        assert result1.credit_score == result2.credit_score
        assert result1.outstanding_accounts == result2.outstanding_accounts
        assert result1.total_outstanding_debt == result2.total_outstanding_debt

    def test_should_generate_scores_in_valid_range(self):
        result = _service().soft_pull(borrower_id=42)

        assert 580 <= result.credit_score <= 799  # 580 + [0, 220)
        assert result.outstanding_accounts >= 2
        assert result.total_outstanding_debt >= 15000
        assert result.oldest_account_years >= 2

    def test_should_fall_back_to_generation_for_unknown_keycloak_id(self):
        result = _service().soft_pull(borrower_id=5, keycloak_user_id="unknown-id")

        assert 580 <= result.credit_score <= 799


class TestHardPull:
    """Hard credit pull tests."""

    def test_should_extend_soft_pull_with_trade_lines(self):
        svc = _service()
        hard = svc.hard_pull(borrower_id=1, keycloak_user_id=SARAH_MITCHELL_ID)
        soft = svc.soft_pull(borrower_id=1, keycloak_user_id=SARAH_MITCHELL_ID)

        # Base fields must match soft pull
        assert hard.credit_score == soft.credit_score
        assert hard.outstanding_accounts == soft.outstanding_accounts
        assert hard.total_outstanding_debt == soft.total_outstanding_debt
        assert hard.derogatory_marks == soft.derogatory_marks

        # Hard-pull-only fields present
        assert len(hard.trade_lines) == min(soft.outstanding_accounts, 6)
        assert isinstance(hard.bankruptcy_flag, bool)

    def test_should_derive_collections_from_derogatory_marks(self):
        # Daniel Ramirez: 3 derogatory marks -> collections = max(0, 3-1) = 2
        result = _service().hard_pull(borrower_id=1, keycloak_user_id=DANIEL_RAMIREZ_ID)

        assert result.derogatory_marks == 3
        assert result.collections_count == 2
        assert result.public_records_count == 1  # derog >= 3

    def test_should_not_flag_bankruptcy_above_580(self):
        result = _service().hard_pull(borrower_id=1, keycloak_user_id=THOMAS_NGUYEN_ID)

        assert result.credit_score == 780
        assert result.bankruptcy_flag is False
        assert result.collections_count == 0  # 0 derogatory marks

    def test_should_generate_valid_trade_line_fields(self):
        result = _service().hard_pull(borrower_id=1, keycloak_user_id=SARAH_MITCHELL_ID)

        valid_statuses = {"current", "late_30", "late_60", "late_90", "collection"}
        for line in result.trade_lines:
            assert line.balance >= 0
            assert line.monthly_payment >= 0
            assert line.status in valid_statuses
            assert line.opened_years_ago >= 1
