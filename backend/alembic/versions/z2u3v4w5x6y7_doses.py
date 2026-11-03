"""A Dose: one giving of a Medication (ADR 060, #368)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "z2u3v4w5x6y7"
down_revision = "y1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("medication_id", UUID(as_uuid=True), sa.ForeignKey("medication_statements.id"), nullable=False, index=True),
        sa.Column("given_at", sa.String(16), nullable=False),
        sa.Column("given_by", sa.String(256)),
        sa.Column("amount", sa.String(256)),
        sa.Column("note", sa.Text()),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id")),
    )


def downgrade() -> None:
    op.drop_table("doses")
