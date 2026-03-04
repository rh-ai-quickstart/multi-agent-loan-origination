# This project was developed with assistance from AI tools.
"""add prequalification_decisions table

Stores the loan officer's pre-qualification decision per application.
One decision per application (UNIQUE on application_id).

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-03-04 13:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prequalification_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(50), nullable=False),
        sa.Column("max_loan_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("estimated_rate", sa.Numeric(5, 3), nullable=False),
        sa.Column("credit_score_at_decision", sa.Integer(), nullable=False),
        sa.Column("dti_at_decision", sa.Numeric(5, 4), nullable=False),
        sa.Column("ltv_at_decision", sa.Numeric(5, 4), nullable=False),
        sa.Column("issued_by", sa.String(255), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("application_id", name="uq_prequal_application"),
    )
    op.create_index(
        "ix_prequalification_decisions_application_id",
        "prequalification_decisions",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_prequalification_decisions_application_id",
        table_name="prequalification_decisions",
    )
    op.drop_table("prequalification_decisions")
