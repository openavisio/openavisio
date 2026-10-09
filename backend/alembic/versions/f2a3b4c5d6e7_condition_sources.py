"""condition_sources: every document that names a condition (#133)

Backfills one source per condition from the existing document_reference_id, so
history starts complete instead of empty.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "f2a3b4c5d6e7"
down_revision = "e1z2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "condition_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("condition_id", UUID(as_uuid=True), sa.ForeignKey("conditions.id"), nullable=False, index=True),
        sa.Column("document_reference_id", UUID(as_uuid=True), sa.ForeignKey("document_references.id"), nullable=False),
        sa.UniqueConstraint("condition_id", "document_reference_id"),
    )
    # gen_random_uuid() is built into Postgres 13+
    op.execute(
        """
        INSERT INTO condition_sources (id, condition_id, document_reference_id, is_deleted)
        SELECT gen_random_uuid(), id, document_reference_id, false
        FROM conditions
        WHERE document_reference_id IS NOT NULL AND is_deleted = false
        """
    )


def downgrade() -> None:
    op.drop_table("condition_sources")
