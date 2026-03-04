# This project was developed with assistance from AI tools.
"""
Summit Cap Financial -- domain models

Mortgage lending lifecycle models covering applications, borrowers,
documents, underwriting conditions/decisions, and audit trail.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from pgvector.sqlalchemy import Vector

from .database import Base
from .enums import (
    ApplicationStage,
    ConditionSeverity,
    ConditionStatus,
    DecisionType,
    DocumentStatus,
    DocumentType,
    EmploymentStatus,
    LoanType,
)


class Borrower(Base):
    """Borrower profile linked to Keycloak identity."""

    __tablename__ = "borrowers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keycloak_user_id = Column(String(255), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    ssn = Column(String(255), nullable=True)
    dob = Column(DateTime(timezone=True), nullable=True)
    employment_status = Column(
        Enum(EmploymentStatus, name="employment_status", native_enum=False),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    application_borrowers = relationship(
        "ApplicationBorrower", back_populates="borrower", cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Borrower(id={self.id}, name='{self.first_name} {self.last_name}')>"


class Application(Base):
    """Mortgage loan application."""

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stage = Column(
        Enum(ApplicationStage, name="application_stage", native_enum=False),
        nullable=False,
        default=ApplicationStage.INQUIRY,
    )
    loan_type = Column(
        Enum(LoanType, name="loan_type", native_enum=False),
        nullable=True,
    )
    property_address = Column(Text, nullable=True)
    loan_amount = Column(Numeric(12, 2), nullable=True)
    property_value = Column(Numeric(12, 2), nullable=True)
    assigned_to = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    le_delivery_date = Column(DateTime(timezone=True), nullable=True)
    cd_delivery_date = Column(DateTime(timezone=True), nullable=True)
    closing_date = Column(DateTime(timezone=True), nullable=True)

    application_borrowers = relationship(
        "ApplicationBorrower", back_populates="application", cascade="all, delete-orphan",
    )
    financials = relationship(
        "ApplicationFinancials", back_populates="application",
        cascade="all, delete-orphan",
    )
    rate_locks = relationship(
        "RateLock", back_populates="application", cascade="all, delete-orphan",
    )
    conditions = relationship(
        "Condition", back_populates="application", cascade="all, delete-orphan",
    )
    decisions = relationship(
        "Decision", back_populates="application", cascade="all, delete-orphan",
    )
    documents = relationship(
        "Document", back_populates="application", cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Application(id={self.id}, stage='{self.stage}')>"


class ApplicationBorrower(Base):
    """Junction table linking applications to borrowers (supports co-borrowers)."""

    __tablename__ = "application_borrowers"
    __table_args__ = (
        UniqueConstraint("application_id", "borrower_id", name="uq_app_borrower"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    borrower_id = Column(
        Integer, ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application = relationship("Application", back_populates="application_borrowers")
    borrower = relationship("Borrower", back_populates="application_borrowers")

    def __repr__(self):
        return (
            f"<ApplicationBorrower(app_id={self.application_id}, "
            f"borrower_id={self.borrower_id}, primary={self.is_primary})>"
        )


class ApplicationFinancials(Base):
    """Financial details for an application, optionally per-borrower."""

    __tablename__ = "application_financials"
    __table_args__ = (
        UniqueConstraint("application_id", "borrower_id", name="uq_app_financials_app_borrower"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    borrower_id = Column(
        Integer, ForeignKey("borrowers.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    gross_monthly_income = Column(Numeric(12, 2), nullable=True)
    monthly_debts = Column(Numeric(12, 2), nullable=True)
    total_assets = Column(Numeric(14, 2), nullable=True)
    credit_score = Column(Integer, nullable=True)
    dti_ratio = Column(Numeric(5, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    application = relationship("Application", back_populates="financials")

    def __repr__(self):
        return f"<ApplicationFinancials(app_id={self.application_id}, credit={self.credit_score})>"


class RateLock(Base):
    """Rate lock on an application."""

    __tablename__ = "rate_locks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    locked_rate = Column(Numeric(5, 3), nullable=False)
    lock_date = Column(DateTime(timezone=True), nullable=False)
    expiration_date = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    application = relationship("Application", back_populates="rate_locks")

    def __repr__(self):
        return f"<RateLock(app_id={self.application_id}, rate={self.locked_rate})>"


class Condition(Base):
    """Underwriting condition on an application."""

    __tablename__ = "conditions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    description = Column(Text, nullable=False)
    severity = Column(
        Enum(ConditionSeverity, name="condition_severity", native_enum=False),
        nullable=False,
    )
    status = Column(
        Enum(ConditionStatus, name="condition_status", native_enum=False),
        nullable=False,
        default=ConditionStatus.OPEN,
    )
    response_text = Column(Text, nullable=True)
    issued_by = Column(String(255), nullable=True)
    cleared_by = Column(String(255), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    iteration_count = Column(Integer, nullable=False, server_default="0", default=0)
    waiver_rationale = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    application = relationship("Application", back_populates="conditions")
    documents = relationship("Document", back_populates="condition")

    def __repr__(self):
        return f"<Condition(id={self.id}, status='{self.status}')>"


class Decision(Base):
    """Underwriting decision on an application."""

    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    decision_type = Column(
        Enum(DecisionType, name="decision_type", native_enum=False),
        nullable=False,
    )
    rationale = Column(Text, nullable=True)
    ai_recommendation = Column(Text, nullable=True)
    decided_by = Column(String(255), nullable=True)
    ai_agreement = Column(Boolean, nullable=True)
    override_rationale = Column(Text, nullable=True)
    denial_reasons = Column(JSONB, nullable=True)
    credit_score_used = Column(Integer, nullable=True)
    credit_score_source = Column(String(100), nullable=True)
    contributing_factors = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application = relationship("Application", back_populates="decisions")

    def __repr__(self):
        return f"<Decision(id={self.id}, type='{self.decision_type}')>"


class Document(Base):
    """Document uploaded for an application."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    borrower_id = Column(
        Integer, ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    condition_id = Column(
        Integer, ForeignKey("conditions.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    doc_type = Column(
        Enum(DocumentType, name="document_type", native_enum=False),
        nullable=False,
    )
    file_path = Column(String(500), nullable=True)
    status = Column(
        Enum(DocumentStatus, name="document_status", native_enum=False),
        nullable=False,
        default=DocumentStatus.UPLOADED,
    )
    quality_flags = Column(Text, nullable=True)
    uploaded_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    application = relationship("Application", back_populates="documents")
    condition = relationship("Condition", back_populates="documents")
    extractions = relationship(
        "DocumentExtraction", back_populates="document", cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Document(id={self.id}, type='{self.doc_type}')>"


class DocumentExtraction(Base):
    """Extracted field from a document."""

    __tablename__ = "document_extractions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    field_name = Column(String(255), nullable=False)
    field_value = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    source_page = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="extractions")

    def __repr__(self):
        return f"<DocumentExtraction(doc_id={self.document_id}, field='{self.field_name}')>"


class AuditEvent(Base):
    """Append-only audit trail. INSERT + SELECT only -- no UPDATE or DELETE."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    prev_hash = Column(String(64), nullable=True)
    user_id = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)
    event_type = Column(String(100), nullable=False, index=True)
    application_id = Column(Integer, nullable=True, index=True)
    decision_id = Column(Integer, nullable=True)
    event_data = Column(JSON, nullable=True)
    session_id = Column(String(255), nullable=True, index=True)

    def __repr__(self):
        return f"<AuditEvent(id={self.id}, type='{self.event_type}')>"


class AuditViolation(Base):
    """Records attempted UPDATE/DELETE on audit_events (trigger-populated)."""

    __tablename__ = "audit_violations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    attempted_operation = Column(String(10), nullable=False)
    db_user = Column(String(255), nullable=False)
    audit_event_id = Column(Integer, nullable=True)


class DemoDataManifest(Base):
    """Tracks demo data seeding for idempotency."""

    __tablename__ = "demo_data_manifest"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seeded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    config_hash = Column(String(64), nullable=False)
    summary = Column(Text, nullable=True)

    def __repr__(self):
        return f"<DemoDataManifest(id={self.id}, seeded_at='{self.seeded_at}')>"


class KBDocument(Base):
    """Compliance knowledge base document (regulation, guideline, or policy)."""

    __tablename__ = "kb_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    tier = Column(Integer, nullable=False, index=True)  # 1=federal, 2=agency, 3=internal
    source_file = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    effective_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chunks = relationship("KBChunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KBDocument(id={self.id}, title='{self.title}', tier={self.tier})>"


class KBChunk(Base):
    """Embedded text chunk from a compliance KB document."""

    __tablename__ = "kb_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer, ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    chunk_text = Column(Text, nullable=False)
    section_ref = Column(String(500), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(Vector(768), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("KBDocument", back_populates="chunks")

    def __repr__(self):
        return f"<KBChunk(id={self.id}, doc_id={self.document_id}, index={self.chunk_index})>"


class CreditReport(Base):
    """Credit bureau report (soft or hard pull)."""

    __tablename__ = "credit_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    borrower_id = Column(
        Integer, ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pull_type = Column(String(10), nullable=False)  # "soft" | "hard"
    credit_score = Column(Integer, nullable=False)  # 300-850
    bureau = Column(String(50), nullable=False)  # "mock_equifax" for MVP
    outstanding_accounts = Column(Integer, nullable=True)
    total_outstanding_debt = Column(Numeric(14, 2), nullable=True)
    derogatory_marks = Column(Integer, nullable=True)
    oldest_account_years = Column(Integer, nullable=True)
    # Hard-pull-only fields
    trade_lines = Column(JSONB, nullable=True)
    collections_count = Column(Integer, nullable=True)
    bankruptcy_flag = Column(Boolean, nullable=True)
    public_records_count = Column(Integer, nullable=True)
    pulled_at = Column(DateTime(timezone=True), nullable=False)
    pulled_by = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    borrower = relationship("Borrower", backref="credit_reports")
    application = relationship("Application", backref="credit_reports")

    def __repr__(self):
        return (
            f"<CreditReport(id={self.id}, borrower_id={self.borrower_id}, "
            f"pull_type='{self.pull_type}', score={self.credit_score})>"
        )


class PrequalificationDecision(Base):
    """Loan officer's pre-qualification decision for an application."""

    __tablename__ = "prequalification_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    product_id = Column(String(50), nullable=False)
    max_loan_amount = Column(Numeric(12, 2), nullable=False)
    estimated_rate = Column(Numeric(5, 3), nullable=False)
    credit_score_at_decision = Column(Integer, nullable=False)
    dti_at_decision = Column(Numeric(5, 4), nullable=False)
    ltv_at_decision = Column(Numeric(5, 4), nullable=False)
    issued_by = Column(String(255), nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application = relationship("Application", backref="prequalification_decision")

    def __repr__(self):
        return (
            f"<PrequalificationDecision(id={self.id}, app_id={self.application_id}, "
            f"product='{self.product_id}')>"
        )


class HmdaDemographic(Base):
    """HMDA demographic data -- isolated in hmda schema."""

    __tablename__ = "demographics"
    __table_args__ = (
        UniqueConstraint("application_id", "borrower_id", name="uq_demographics_app_borrower"),
        {"schema": "hmda"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, nullable=False, index=True)
    borrower_id = Column(Integer, nullable=True, index=True)
    race = Column(String(100), nullable=True)
    ethnicity = Column(String(100), nullable=True)
    sex = Column(String(50), nullable=True)
    age = Column(String(20), nullable=True)
    race_method = Column(String(50), nullable=True)
    ethnicity_method = Column(String(50), nullable=True)
    sex_method = Column(String(50), nullable=True)
    age_method = Column(String(50), nullable=True)
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<HmdaDemographic(id={self.id}, app_id={self.application_id})>"


class HmdaLoanData(Base):
    """Non-demographic HMDA-reportable loan data -- snapshot at underwriting submission."""

    __tablename__ = "loan_data"
    __table_args__ = {"schema": "hmda"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, nullable=False, unique=True, index=True)
    gross_monthly_income = Column(Numeric(12, 2), nullable=True)
    dti_ratio = Column(Numeric(5, 4), nullable=True)
    credit_score = Column(Integer, nullable=True)
    loan_type = Column(String(50), nullable=True)
    loan_purpose = Column(String(50), nullable=True)
    property_location = Column(Text, nullable=True)
    interest_rate = Column(Numeric(5, 3), nullable=True)
    total_fees = Column(Numeric(10, 2), nullable=True)
    snapshot_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<HmdaLoanData(id={self.id}, app_id={self.application_id})>"
