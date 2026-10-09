"""Emergency Plan, one per Patient (ADR 048)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "o1j2k3l4m5n6"
down_revision = "n0i1j2k3l4m5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emergency_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, unique=True),
        sa.Column("situations", JSONB(), nullable=False, server_default="[]"),
        sa.Column("contacts", JSONB(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("document_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("emergency_plans")
