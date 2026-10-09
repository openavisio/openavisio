"""encryption mandatory: drop is_encrypted, add kek_version

Revision ID: u1p2q3r4s5t6
Revises: t0o1p2q3r4s5
Create Date: 2026-07-02

ADR-022: every stored file is envelope-encrypted, so the is_encrypted flag is
removed (invariant: encrypted_dek IS NOT NULL). kek_version records which KEK
generation wrapped each document's DEK, enabling future key rotation.
"""
from alembic import op
import sqlalchemy as sa

revision = "u1p2q3r4s5t6"
down_revision = "t0o1p2q3r4s5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_references",
        sa.Column("kek_version", sa.SmallInteger(), nullable=False, server_default="1"),
    )
    op.drop_column("document_references", "is_encrypted")


def downgrade() -> None:
    op.add_column(
        "document_references",
        sa.Column("is_encrypted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_column("document_references", "kek_version")
