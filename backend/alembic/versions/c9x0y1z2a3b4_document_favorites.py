"""document favorites — pin the documents you reach for at every appointment"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "c9x0y1z2a3b4"
down_revision = "b8w9x0y1z2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_favorites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("document_references.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false()),
        sa.UniqueConstraint("user_id", "document_id", name="uq_document_favorite"),
    )


def downgrade() -> None:
    op.drop_table("document_favorites")
