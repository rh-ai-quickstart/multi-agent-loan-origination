# This project was developed with assistance from AI tools.
"""add predictive model fields to risk_assessments

Stores the external ML model prediction result and availability flag
alongside the existing rule-based risk factors.

Revision ID: 3f0a759b847d
Revises: b9e855e06fdb
Create Date: 2026-04-13 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3f0a759b847d"
down_revision = "b9e855e06fdb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "risk_assessments",
        sa.Column("predictive_model_result", sa.String(50), nullable=True),
    )
    op.add_column(
        "risk_assessments",
        sa.Column("predictive_model_available", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("risk_assessments", "predictive_model_available")
    op.drop_column("risk_assessments", "predictive_model_result")
