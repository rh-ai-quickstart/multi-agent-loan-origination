# This project was developed with assistance from AI tools.
"""Expand document_type enum with mortgage-specific types.

Replaces generic 'id' and 'insurance' with specific document types:
- id -> drivers_license, passport
- insurance -> homeowners_insurance, title_insurance, flood_insurance
- Added: purchase_agreement, gift_letter

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-03-19
"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None

# New values to add
_NEW_VALUES = [
    "drivers_license",
    "passport",
    "homeowners_insurance",
    "title_insurance",
    "flood_insurance",
    "purchase_agreement",
    "gift_letter",
]

# Old values to migrate
_RENAMES = {
    "id": "drivers_license",
    "insurance": "homeowners_insurance",
}


def upgrade() -> None:
    # Add new enum values
    for val in _NEW_VALUES:
        op.execute(f"ALTER TYPE documenttype ADD VALUE IF NOT EXISTS '{val}'")

    # Migrate existing rows from old values to new values
    for old_val, new_val in _RENAMES.items():
        op.execute(
            f"UPDATE documents SET doc_type = '{new_val}' WHERE doc_type = '{old_val}'"
        )


def downgrade() -> None:
    # Migrate rows back to old values
    for old_val, new_val in _RENAMES.items():
        op.execute(
            f"UPDATE documents SET doc_type = '{old_val}' WHERE doc_type = '{new_val}'"
        )
    # PostgreSQL doesn't support removing enum values; would need to recreate the type
