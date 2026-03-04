# This project was developed with assistance from AI tools.
"""add credit_reports table

Stores mock credit bureau pull results (soft and hard) for
pre-qualification and underwriting workflows.

Revision ID: b4c5d6e7f8a9
Revises: a509624ca371
Create Date: 2026-03-04 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "b4c5d6e7f8a9"
down_revision = "a509624ca371"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("pull_type", sa.String(10), nullable=False),
        sa.Column("credit_score", sa.Integer(), nullable=False),
        sa.Column("bureau", sa.String(50), nullable=False),
        sa.Column("outstanding_accounts", sa.Integer(), nullable=True),
        sa.Column("total_outstanding_debt", sa.Numeric(14, 2), nullable=True),
        sa.Column("derogatory_marks", sa.Integer(), nullable=True),
        sa.Column("oldest_account_years", sa.Integer(), nullable=True),
        sa.Column("trade_lines", JSONB(), nullable=True),
        sa.Column("collections_count", sa.Integer(), nullable=True),
        sa.Column("bankruptcy_flag", sa.Boolean(), nullable=True),
        sa.Column("public_records_count", sa.Integer(), nullable=True),
        sa.Column("pulled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pulled_by", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["borrower_id"], ["borrowers.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_reports_borrower_id", "credit_reports", ["borrower_id"])
    op.create_index("ix_credit_reports_application_id", "credit_reports", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_credit_reports_application_id", table_name="credit_reports")
    op.drop_index("ix_credit_reports_borrower_id", table_name="credit_reports")
    op.drop_table("credit_reports")
