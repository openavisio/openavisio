"""add encrypted_dek to document_references

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-06-06

"""
from alembic import op
import sqlalchemy as sa

revision = "m3h4i5j6k7l8"
down_revision = "l2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_references",
        sa.Column("encrypted_dek", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_references", "encrypted_dek")
