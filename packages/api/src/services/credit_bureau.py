# This project was developed with assistance from AI tools.
"""Mock credit bureau service for simulated soft/hard pulls.

In production, this would be replaced with real API calls to
Equifax/Experian/TransUnion. The mock generates deterministic data
for seed borrowers and reproducible data for unknown borrowers.

Simulated for demonstration purposes -- not real credit data.
"""

import hashlib
import logging
from decimal import Decimal

from ..schemas.credit import HardPullResult, SoftPullResult, TradeLineDetail

logger = logging.getLogger(__name__)

# Deterministic credit profiles for seed borrowers keyed by credit_score.
# When a borrower's self-reported score matches a known fixture value,
# the mock returns consistent supplementary data.
_SEED_PROFILES: dict[int, dict] = {
    742: {
        "outstanding_accounts": 4,
        "total_outstanding_debt": Decimal("45200.00"),
        "derogatory_marks": 0,
        "oldest_account_years": 12,
    },
    688: {
        "outstanding_accounts": 6,
        "total_outstanding_debt": Decimal("67800.00"),
        "derogatory_marks": 1,
        "oldest_account_years": 7,
    },
    735: {
        "outstanding_accounts": 3,
        "total_outstanding_debt": Decimal("38500.00"),
        "derogatory_marks": 0,
        "oldest_account_years": 10,
    },
    765: {
        "outstanding_accounts": 5,
        "total_outstanding_debt": Decimal("52000.00"),
        "derogatory_marks": 0,
        "oldest_account_years": 15,
    },
    710: {
        "outstanding_accounts": 5,
        "total_outstanding_debt": Decimal("58300.00"),
        "derogatory_marks": 1,
        "oldest_account_years": 8,
    },
    695: {
        "outstanding_accounts": 7,
        "total_outstanding_debt": Decimal("71200.00"),
        "derogatory_marks": 2,
        "oldest_account_years": 6,
    },
    780: {
        "outstanding_accounts": 3,
        "total_outstanding_debt": Decimal("28900.00"),
        "derogatory_marks": 0,
        "oldest_account_years": 18,
    },
    725: {
        "outstanding_accounts": 4,
        "total_outstanding_debt": Decimal("41500.00"),
        "derogatory_marks": 0,
        "oldest_account_years": 9,
    },
    612: {
        "outstanding_accounts": 8,
        "total_outstanding_debt": Decimal("89500.00"),
        "derogatory_marks": 3,
        "oldest_account_years": 5,
    },
    648: {
        "outstanding_accounts": 7,
        "total_outstanding_debt": Decimal("78200.00"),
        "derogatory_marks": 2,
        "oldest_account_years": 6,
    },
    655: {
        "outstanding_accounts": 6,
        "total_outstanding_debt": Decimal("72100.00"),
        "derogatory_marks": 2,
        "oldest_account_years": 7,
    },
    632: {
        "outstanding_accounts": 9,
        "total_outstanding_debt": Decimal("95300.00"),
        "derogatory_marks": 4,
        "oldest_account_years": 4,
    },
}


def _hash_to_int(value: int, modulus: int, salt: str = "") -> int:
    """Deterministic pseudo-random int from a borrower_id."""
    h = hashlib.sha256(f"{value}:{salt}".encode()).hexdigest()
    return int(h[:8], 16) % modulus


def _generate_profile(borrower_id: int) -> dict:
    """Generate plausible credit profile data from borrower_id hash."""
    score = 580 + _hash_to_int(borrower_id, 220, "score")
    derog = 0 if score > 700 else _hash_to_int(borrower_id, 3, "derog")
    accounts = 2 + _hash_to_int(borrower_id, 8, "accounts")
    debt_base = 15000 + _hash_to_int(borrower_id, 80000, "debt")
    oldest = 2 + _hash_to_int(borrower_id, 18, "oldest")
    return {
        "credit_score": score,
        "outstanding_accounts": accounts,
        "total_outstanding_debt": Decimal(str(debt_base)),
        "derogatory_marks": derog,
        "oldest_account_years": oldest,
    }


def _generate_trade_lines(borrower_id: int, num_accounts: int) -> list[TradeLineDetail]:
    """Generate mock trade line details for a hard pull."""
    account_types = ["credit_card", "auto_loan", "student_loan", "mortgage", "personal_loan"]
    statuses = ["current", "current", "current", "late_30", "late_60"]
    lines = []
    for i in range(min(num_accounts, 6)):
        balance = Decimal(str(5000 + _hash_to_int(borrower_id, 30000, f"bal_{i}")))
        limit_val = balance + Decimal(str(2000 + _hash_to_int(borrower_id, 15000, f"lim_{i}")))
        payment = Decimal(str(50 + _hash_to_int(borrower_id, 500, f"pay_{i}")))
        lines.append(
            TradeLineDetail(
                account_type=account_types[i % len(account_types)],
                balance=balance,
                credit_limit=limit_val if i < 3 else None,
                monthly_payment=payment,
                status=statuses[_hash_to_int(borrower_id, len(statuses), f"status_{i}")],
                opened_years_ago=1 + _hash_to_int(borrower_id, 15, f"opened_{i}"),
            )
        )
    return lines


class CreditBureauService:
    """Mock credit bureau for simulated soft/hard pulls.

    In production, this would be replaced with real API calls
    to Equifax/Experian/TransUnion.
    """

    def soft_pull(
        self,
        borrower_id: int,
        credit_score_hint: int | None = None,
    ) -> SoftPullResult:
        """Simulate a soft credit pull.

        Args:
            borrower_id: Internal borrower ID.
            credit_score_hint: Self-reported score from financials. If it matches
                a seed profile, deterministic data is returned.

        Returns:
            SoftPullResult with credit data.
        """
        if credit_score_hint and credit_score_hint in _SEED_PROFILES:
            profile = _SEED_PROFILES[credit_score_hint]
            return SoftPullResult(
                credit_score=credit_score_hint,
                **profile,
            )

        profile = _generate_profile(borrower_id)
        return SoftPullResult(
            credit_score=profile["credit_score"],
            outstanding_accounts=profile["outstanding_accounts"],
            total_outstanding_debt=profile["total_outstanding_debt"],
            derogatory_marks=profile["derogatory_marks"],
            oldest_account_years=profile["oldest_account_years"],
        )

    def hard_pull(
        self,
        borrower_id: int,
        credit_score_hint: int | None = None,
    ) -> HardPullResult:
        """Simulate a hard credit pull.

        Args:
            borrower_id: Internal borrower ID.
            credit_score_hint: Self-reported score from financials.

        Returns:
            HardPullResult with full credit data including trade lines.
        """
        soft = self.soft_pull(borrower_id, credit_score_hint)

        num_accounts = soft.outstanding_accounts
        trade_lines = _generate_trade_lines(borrower_id, num_accounts)
        derog = soft.derogatory_marks
        collections = max(0, derog - 1) if derog > 0 else 0
        bankruptcy = soft.credit_score < 580
        public_records = 1 if bankruptcy else (1 if derog >= 3 else 0)

        return HardPullResult(
            credit_score=soft.credit_score,
            bureau=soft.bureau,
            outstanding_accounts=soft.outstanding_accounts,
            total_outstanding_debt=soft.total_outstanding_debt,
            derogatory_marks=soft.derogatory_marks,
            oldest_account_years=soft.oldest_account_years,
            trade_lines=trade_lines,
            collections_count=collections,
            bankruptcy_flag=bankruptcy,
            public_records_count=public_records,
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: CreditBureauService | None = None


def get_credit_bureau_service() -> CreditBureauService:
    """Return the CreditBureauService singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        _service = CreditBureauService()
    return _service
