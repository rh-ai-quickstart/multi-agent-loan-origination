# This project was developed with assistance from AI tools.
"""add recommendation columns to risk_assessments

Stores the preliminary recommendation output alongside the risk
assessment so the UI can display it without a page refresh.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-03-04 16:30:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("risk_assessments", sa.Column("recommendation", sa.String(50), nullable=True))
    op.add_column("risk_assessments", sa.Column("recommendation_rationale", JSONB(), nullable=True))
    op.add_column("risk_assessments", sa.Column("recommendation_conditions", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("risk_assessments", "recommendation_conditions")
    op.drop_column("risk_assessments", "recommendation_rationale")
    op.drop_column("risk_assessments", "recommendation")
