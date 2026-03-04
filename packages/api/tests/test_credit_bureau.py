# This project was developed with assistance from AI tools.
"""Tests for mock credit bureau service."""

from decimal import Decimal

import pytest

from src.services.credit_bureau import CreditBureauService


@pytest.fixture
def service():
    return CreditBureauService()


class TestSoftPull:
    """Soft credit pull tests."""

    def test_should_return_seed_profile_when_score_matches_known_fixture(self, service):
        result = service.soft_pull(borrower_id=1, credit_score_hint=742)

        assert result.credit_score == 742
        assert result.bureau == "mock_equifax"
        assert result.outstanding_accounts == 4
        assert result.total_outstanding_debt == Decimal("45200.00")
        assert result.derogatory_marks == 0
        assert result.oldest_account_years == 12

    def test_should_return_generated_profile_when_no_score_hint(self, service):
        result = service.soft_pull(borrower_id=42)

        assert 300 <= result.credit_score <= 850
        assert result.bureau == "mock_equifax"
        assert result.outstanding_accounts >= 2
        assert result.total_outstanding_debt > 0
        assert result.derogatory_marks >= 0
        assert result.oldest_account_years >= 2

    def test_should_return_deterministic_results_for_same_borrower(self, service):
        result1 = service.soft_pull(borrower_id=99)
        result2 = service.soft_pull(borrower_id=99)

        assert result1.credit_score == result2.credit_score
        assert result1.outstanding_accounts == result2.outstanding_accounts
        assert result1.total_outstanding_debt == result2.total_outstanding_debt

    def test_should_return_different_results_for_different_borrowers(self, service):
        result1 = service.soft_pull(borrower_id=100)
        result2 = service.soft_pull(borrower_id=200)

        # At least one field should differ (statistically guaranteed by hash)
        fields_differ = (
            result1.credit_score != result2.credit_score
            or result1.outstanding_accounts != result2.outstanding_accounts
            or result1.total_outstanding_debt != result2.total_outstanding_debt
        )
        assert fields_differ

    @pytest.mark.parametrize("score", [612, 648, 655, 632])
    def test_should_return_seed_profile_for_denied_borrower_scores(self, service, score):
        result = service.soft_pull(borrower_id=1, credit_score_hint=score)

        assert result.credit_score == score
        assert result.derogatory_marks >= 2

    def test_should_generate_when_score_hint_not_in_seed_profiles(self, service):
        result = service.soft_pull(borrower_id=5, credit_score_hint=999)

        # 999 is not a seed profile score, so generated data is used
        assert 300 <= result.credit_score <= 850


class TestHardPull:
    """Hard credit pull tests."""

    def test_should_include_trade_lines(self, service):
        result = service.hard_pull(borrower_id=1, credit_score_hint=742)

        assert result.credit_score == 742
        assert len(result.trade_lines) > 0
        assert result.collections_count >= 0
        assert isinstance(result.bankruptcy_flag, bool)
        assert result.public_records_count >= 0

    def test_should_have_valid_trade_line_fields(self, service):
        result = service.hard_pull(borrower_id=1, credit_score_hint=742)

        for line in result.trade_lines:
            assert line.account_type
            assert line.balance >= 0
            assert line.monthly_payment >= 0
            assert line.status in {"current", "late_30", "late_60", "late_90", "collection"}
            assert line.opened_years_ago >= 1

    def test_should_not_flag_bankruptcy_for_good_credit(self, service):
        result = service.hard_pull(borrower_id=1, credit_score_hint=780)

        assert result.bankruptcy_flag is False

    def test_should_include_soft_pull_fields(self, service):
        hard = service.hard_pull(borrower_id=1, credit_score_hint=742)
        soft = service.soft_pull(borrower_id=1, credit_score_hint=742)

        assert hard.credit_score == soft.credit_score
        assert hard.outstanding_accounts == soft.outstanding_accounts
        assert hard.total_outstanding_debt == soft.total_outstanding_debt
        assert hard.derogatory_marks == soft.derogatory_marks

    def test_should_return_collections_for_low_credit(self, service):
        result = service.hard_pull(borrower_id=1, credit_score_hint=612)

        # 612 has 3 derogatory marks -> collections_count = max(0, 3-1) = 2
        assert result.collections_count == 2
        assert result.derogatory_marks == 3


class TestSingleton:
    """Singleton accessor tests."""

    def test_should_return_same_instance(self):
        from src.services.credit_bureau import get_credit_bureau_service

        svc1 = get_credit_bureau_service()
        svc2 = get_credit_bureau_service()

        assert svc1 is svc2
        assert isinstance(svc1, CreditBureauService)
