"""Intake Forms and History Facts (ADR 047)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "s5n6o7p8q9r0"
down_revision = "r4m5n6o7p8q9"
branch_labels = None
depends_on = None


def _base():
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false()),
    ]


def upgrade() -> None:
    op.create_table(
        "intake_forms",
        *_base(),
        sa.Column("title", sa.String(256)),
        sa.Column("file_name", sa.String(512)),
        sa.Column("content_type", sa.String(100)),
        sa.Column("size", sa.BigInteger()),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("encrypted_dek", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(20), server_default="reading"),
        sa.Column("processing_error", sa.Text()),
        sa.Column("sheet", sa.Text()),
        sa.Column("released_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "history_facts",
        *_base(),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("aging", sa.String(20), nullable=False),
        sa.Column("confirmed_on", sa.String(10), nullable=False),
        sa.Column("source", sa.String(20), server_default="caregiver"),
        sa.Column("document_reference_id", UUID(as_uuid=True), sa.ForeignKey("document_references.id")),
        sa.Column("intake_form_id", UUID(as_uuid=True), sa.ForeignKey("intake_forms.id", ondelete="SET NULL")),
    )


def downgrade() -> None:
    op.drop_table("history_facts")
    op.drop_table("intake_forms")
