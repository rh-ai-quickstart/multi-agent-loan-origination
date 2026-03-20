# This project was developed with assistance from AI tools.
"""
Domain enums for the mortgage lending lifecycle.

Shared domain types used by both SQLAlchemy models (db package)
and Pydantic schemas (api package).
"""

import enum


class ApplicationStage(str, enum.Enum):
    INQUIRY = "inquiry"
    PREQUALIFICATION = "prequalification"
    APPLICATION = "application"
    PROCESSING = "processing"
    UNDERWRITING = "underwriting"
    CONDITIONAL_APPROVAL = "conditional_approval"
    CLEAR_TO_CLOSE = "clear_to_close"
    CLOSED = "closed"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"


    @classmethod
    def terminal_stages(cls) -> frozenset["ApplicationStage"]:
        """Stages where an application is no longer active."""
        return frozenset({cls.CLOSED, cls.DENIED, cls.WITHDRAWN})

    @classmethod
    def valid_transitions(cls) -> dict["ApplicationStage", frozenset["ApplicationStage"]]:
        """Allowed stage transitions in the lending lifecycle."""
        return {
            cls.INQUIRY: frozenset({cls.PREQUALIFICATION, cls.APPLICATION, cls.WITHDRAWN}),
            cls.PREQUALIFICATION: frozenset({cls.APPLICATION, cls.DENIED, cls.WITHDRAWN}),
            cls.APPLICATION: frozenset({cls.PROCESSING, cls.DENIED, cls.WITHDRAWN}),
            cls.PROCESSING: frozenset({cls.UNDERWRITING, cls.DENIED, cls.WITHDRAWN}),
            cls.UNDERWRITING: frozenset(
                {cls.CONDITIONAL_APPROVAL, cls.CLEAR_TO_CLOSE, cls.DENIED, cls.WITHDRAWN}
            ),
            cls.CONDITIONAL_APPROVAL: frozenset(
                {cls.CLEAR_TO_CLOSE, cls.DENIED, cls.WITHDRAWN}
            ),
            cls.CLEAR_TO_CLOSE: frozenset({cls.CLOSED, cls.WITHDRAWN}),
            cls.CLOSED: frozenset(),
            cls.DENIED: frozenset(),
            cls.WITHDRAWN: frozenset(),
        }


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    PROSPECT = "prospect"
    BORROWER = "borrower"
    LOAN_OFFICER = "loan_officer"
    UNDERWRITER = "underwriter"
    CEO = "ceo"


class LoanType(str, enum.Enum):
    CONVENTIONAL_30 = "conventional_30"
    CONVENTIONAL_15 = "conventional_15"
    FHA = "fha"
    VA = "va"
    JUMBO = "jumbo"
    USDA = "usda"
    ARM = "arm"


class DocumentType(str, enum.Enum):
    W2 = "w2"
    PAY_STUB = "pay_stub"
    TAX_RETURN = "tax_return"
    BANK_STATEMENT = "bank_statement"
    DRIVERS_LICENSE = "drivers_license"
    PASSPORT = "passport"
    PROPERTY_APPRAISAL = "property_appraisal"
    HOMEOWNERS_INSURANCE = "homeowners_insurance"
    TITLE_INSURANCE = "title_insurance"
    FLOOD_INSURANCE = "flood_insurance"
    PURCHASE_AGREEMENT = "purchase_agreement"
    GIFT_LETTER = "gift_letter"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSING_COMPLETE = "processing_complete"
    PROCESSING_FAILED = "processing_failed"
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    FLAGGED_FOR_RESUBMISSION = "flagged_for_resubmission"
    REJECTED = "rejected"


class ConditionSeverity(str, enum.Enum):
    PRIOR_TO_APPROVAL = "prior_to_approval"
    PRIOR_TO_DOCS = "prior_to_docs"
    PRIOR_TO_CLOSING = "prior_to_closing"
    PRIOR_TO_FUNDING = "prior_to_funding"


class ConditionStatus(str, enum.Enum):
    OPEN = "open"
    RESPONDED = "responded"
    UNDER_REVIEW = "under_review"
    CLEARED = "cleared"
    WAIVED = "waived"
    ESCALATED = "escalated"


class EmploymentStatus(str, enum.Enum):
    W2_EMPLOYEE = "w2_employee"
    SELF_EMPLOYED = "self_employed"
    RETIRED = "retired"
    UNEMPLOYED = "unemployed"
    OTHER = "other"


class DecisionType(str, enum.Enum):
    APPROVED = "approved"
    CONDITIONAL_APPROVAL = "conditional_approval"
    SUSPENDED = "suspended"
    DENIED = "denied"
