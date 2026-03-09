# This project was developed with assistance from AI tools.
"""add risk_assessments and compliance_results tables

Persists underwriter risk assessment and compliance check results
so the UI can fetch and display them.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-03-04 14:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("dti_value", sa.Float(), nullable=True),
        sa.Column("dti_rating", sa.String(20), nullable=True),
        sa.Column("ltv_value", sa.Float(), nullable=True),
        sa.Column("ltv_rating", sa.String(20), nullable=True),
        sa.Column("credit_value", sa.Integer(), nullable=True),
        sa.Column("credit_rating", sa.String(20), nullable=True),
        sa.Column("credit_source", sa.String(50), nullable=True),
        sa.Column("income_stability_value", sa.String(255), nullable=True),
        sa.Column("income_stability_rating", sa.String(20), nullable=True),
        sa.Column("asset_sufficiency_value", sa.Float(), nullable=True),
        sa.Column("asset_sufficiency_rating", sa.String(20), nullable=True),
        sa.Column("compensating_factors", JSONB(), nullable=True),
        sa.Column("warnings", JSONB(), nullable=True),
        sa.Column("overall_risk", sa.String(20), nullable=True),
        sa.Column("assessed_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_risk_assessments_application_id",
        "risk_assessments",
        ["application_id"],
    )

    op.create_table(
        "compliance_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("ecoa_status", sa.String(30), nullable=True),
        sa.Column("ecoa_rationale", sa.Text(), nullable=True),
        sa.Column("ecoa_details", JSONB(), nullable=True),
        sa.Column("atr_qm_status", sa.String(30), nullable=True),
        sa.Column("atr_qm_rationale", sa.Text(), nullable=True),
        sa.Column("atr_qm_details", JSONB(), nullable=True),
        sa.Column("trid_status", sa.String(30), nullable=True),
        sa.Column("trid_rationale", sa.Text(), nullable=True),
        sa.Column("trid_details", JSONB(), nullable=True),
        sa.Column("overall_status", sa.String(30), nullable=True),
        sa.Column("can_proceed", sa.Boolean(), nullable=True),
        sa.Column("checked_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_results_application_id",
        "compliance_results",
        ["application_id"],
    )

    # Grant access to app role if it exists (deployed environments only)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mortgage_ai_app') THEN
                EXECUTE 'GRANT SELECT, INSERT ON risk_assessments TO mortgage_ai_app';
                EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE risk_assessments_id_seq TO mortgage_ai_app';
                EXECUTE 'GRANT SELECT, INSERT ON compliance_results TO mortgage_ai_app';
                EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE compliance_results_id_seq TO mortgage_ai_app';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.drop_index("ix_compliance_results_application_id", table_name="compliance_results")
    op.drop_table("compliance_results")
    op.drop_index("ix_risk_assessments_application_id", table_name="risk_assessments")
    op.drop_table("risk_assessments")
