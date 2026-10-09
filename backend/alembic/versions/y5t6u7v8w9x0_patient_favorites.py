"""patient favorites (#70)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "y5t6u7v8w9x0"
down_revision = "x4s5t6u7v8w9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_favorites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false()),
        sa.UniqueConstraint("user_id", "patient_id", name="uq_patient_favorite"),
    )


def downgrade() -> None:
    op.drop_table("patient_favorites")
