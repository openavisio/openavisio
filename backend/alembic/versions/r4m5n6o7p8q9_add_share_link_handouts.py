"""A Handout frozen into a Document Share Link (ADR 048)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "r4m5n6o7p8q9"
down_revision = "q3l4m5n6o7p8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_share_link_handouts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("share_link_id", UUID(as_uuid=True), sa.ForeignKey("document_share_links.id"), nullable=False, unique=True),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("variant", sa.String(20), nullable=False),
        sa.Column("lang", sa.String(2), nullable=False),
        sa.Column("pdf", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_dek", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("document_share_link_handouts")
