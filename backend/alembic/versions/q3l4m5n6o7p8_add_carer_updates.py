"""Carer Updates (ADR 049)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "q3l4m5n6o7p8"
down_revision = "p2k3l4m5n6o7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "carer_updates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("correspondent_id", UUID(as_uuid=True), sa.ForeignKey("correspondents.id"), nullable=False),
        sa.Column("person", sa.String(256), nullable=True),
        sa.Column("day", sa.String(10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("retold", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("carer_updates")
