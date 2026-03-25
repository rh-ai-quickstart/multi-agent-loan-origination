# This project was developed with assistance from AI tools.
"""Expand document_type enum with mortgage-specific types.

Replaces generic 'id' and 'insurance' with specific document types:
- id -> drivers_license, passport
- insurance -> homeowners_insurance, title_insurance, flood_insurance
- Added: purchase_agreement, gift_letter

Revision ID: b9e855e06fdb
Revises: e7f8a9b0c1d2
Create Date: 2026-03-19
"""

from alembic import op

revision = "b9e855e06fdb"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None

# Old values to migrate (doc_type is a non-native enum stored as varchar)
_RENAMES = {
    "id": "drivers_license",
    "insurance": "homeowners_insurance",
}


def upgrade() -> None:
    # Migrate existing rows from old values to new values.
    # New enum values (passport, title_insurance, etc.) don't need a schema change
    # because doc_type uses native_enum=False (stored as varchar).
    for old_val, new_val in _RENAMES.items():
        op.execute(
            f"UPDATE documents SET doc_type = '{new_val}' WHERE doc_type = '{old_val}'"
        )


def downgrade() -> None:
    for old_val, new_val in _RENAMES.items():
        op.execute(
            f"UPDATE documents SET doc_type = '{old_val}' WHERE doc_type = '{new_val}'"
        )
