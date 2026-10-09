"""Pflegegrad gradings as records with history and module scores (ADR 042)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "m9h0i1j2k3l4"
down_revision = "l8g9h0i1j2k3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "einstufungen",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("pflegegrad", sa.Integer(), nullable=True),
        sa.Column("total_points", sa.Float(), nullable=True),
        sa.Column("valid_from", sa.String(50), nullable=True),
        sa.Column("valid_until", sa.String(50), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("authority", sa.String(256), nullable=True),
        sa.Column("file_reference", sa.String(128), nullable=True),
        # § 15 SGB XI, in the order the law numbers them
        sa.Column("module_mobility", sa.Float(), nullable=True),
        sa.Column("module_cognitive", sa.Float(), nullable=True),
        sa.Column("module_behaviour", sa.Float(), nullable=True),
        sa.Column("module_self_care", sa.Float(), nullable=True),
        sa.Column("module_therapy_demands", sa.Float(), nullable=True),
        sa.Column("module_daily_life", sa.Float(), nullable=True),
        sa.Column("source", sa.String(20), server_default="manual"),
        sa.Column("document_reference_id", UUID(as_uuid=True), sa.ForeignKey("document_references.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("einstufungen")
