"""per-patient KEK keystore (ADR-031, #76)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "a7v8w9x0y1z2"
down_revision = "z6u7v8w9x0y1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wrapped_kek", sa.LargeBinary(), nullable=False),
        sa.Column("kek_version", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false()),
        sa.UniqueConstraint("patient_id", name="uq_patient_keys_patient_id"),
    )
    op.create_index("ix_patient_keys_patient_id", "patient_keys", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_patient_keys_patient_id", table_name="patient_keys")
    op.drop_table("patient_keys")
