# This project was developed with assistance from AI tools.
"""Tests for compliance KB conflict detection."""

from src.services.compliance.knowledge_base.conflict import detect_conflicts
from src.services.compliance.knowledge_base.search import KBSearchResult


def _make_result(
    chunk_text: str,
    tier: int,
    source: str = "Test Doc",
    section: str | None = None,
) -> KBSearchResult:
    """Create a KBSearchResult for testing."""
    tier_labels = {1: "Federal Regulation", 2: "Agency Guideline", 3: "Internal Policy"}
    return KBSearchResult(
        chunk_text=chunk_text,
        source_document=source,
        section_ref=section,
        tier=tier,
        tier_label=tier_labels.get(tier, f"Tier {tier}"),
        similarity=0.8,
        boosted_similarity=0.8,
        effective_date=None,
    )


class TestDetectConflicts:
    """Tests for conflict detection heuristics."""

    def test_numeric_threshold_across_tiers(self):
        """DTI 43% federal vs 40% internal should flag numeric_threshold."""
        results = [
            _make_result(
                "The QM safe harbor requires DTI not exceed 43%",
                tier=1,
                source="ATR/QM Rule",
            ),
            _make_result(
                "The Company sets maximum DTI at 40%",
                tier=3,
                source="Internal Policies",
            ),
        ]
        conflicts = detect_conflicts(results)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "numeric_threshold"
        assert "43" in conflicts[0].description
        assert "40" in conflicts[0].description

    def test_contradictory_directive_flagged(self):
        """'must' vs 'must not' across results should flag contradictory_directive."""
        results = [
            _make_result(
                "The lender must provide the appraisal copy to the applicant",
                tier=1,
            ),
            _make_result(
                "The lender must not share appraisal details before final review",
                tier=3,
            ),
        ]
        conflicts = detect_conflicts(results)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "contradictory_directive"

    def test_same_tier_divergence(self):
        """Two agency results with different limits should flag same_tier."""
        results = [
            _make_result(
                "Maximum DTI ratio is 50% with DU approval",
                tier=2,
                source="Fannie Mae",
            ),
            _make_result(
                "Back-end ratio must not exceed 43%",
                tier=2,
                source="FHA Guidelines",
            ),
        ]
        conflicts = detect_conflicts(results)
        assert len(conflicts) >= 1
        type_found = any(c.conflict_type == "same_tier" for c in conflicts)
        assert type_found

    def test_no_false_positives_complementary(self):
        """Different topics should not be flagged as conflicts."""
        results = [
            _make_result(
                "The Loan Estimate must be delivered within 3 business days",
                tier=1,
                source="TRID Rule",
            ),
            _make_result(
                "All properties must meet minimum property requirements",
                tier=2,
                source="FHA Guidelines",
            ),
        ]
        conflicts = detect_conflicts(results)
        assert len(conflicts) == 0

    def test_empty_results_no_conflicts(self):
        """Empty input should return no conflicts."""
        assert detect_conflicts([]) == []

    def test_single_result_no_conflicts(self):
        """Single result cannot have conflicts."""
        results = [_make_result("Some text about 43% DTI", tier=1)]
        assert detect_conflicts(results) == []
