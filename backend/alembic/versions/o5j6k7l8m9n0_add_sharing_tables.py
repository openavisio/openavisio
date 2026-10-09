"""add sharing tables (sharing_purposes, shares, share_declines)

Revision ID: o5j6k7l8m9n0
Revises: m3h4i5j6k7l8
Create Date: 2026-06-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "o5j6k7l8m9n0"
down_revision = "m3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sharing_purposes",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("identification_mode", sa.String(20), nullable=False, server_default="identified"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sharing_purposes_status", "sharing_purposes", ["status"])

    op.create_table(
        "shares",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sharing_purpose_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("consented_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("consented_legal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["sharing_purpose_id"], ["sharing_purposes.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["document_references.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["consented_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sharing_purpose_id", "document_id", name="uq_share_purpose_document"),
    )
    op.create_index("ix_shares_sharing_purpose_id", "shares", ["sharing_purpose_id"])
    op.create_index("ix_shares_document_id", "shares", ["document_id"])
    op.create_index("ix_shares_patient_id", "shares", ["patient_id"])
    op.create_index("ix_shares_status", "shares", ["status"])

    op.create_table(
        "share_declines",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sharing_purpose_id", UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), nullable=False),
        sa.Column("declined_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["sharing_purpose_id"], ["sharing_purposes.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["declined_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sharing_purpose_id", "patient_id", name="uq_decline_purpose_patient"),
    )
    op.create_index("ix_share_declines_sharing_purpose_id", "share_declines", ["sharing_purpose_id"])
    op.create_index("ix_share_declines_patient_id", "share_declines", ["patient_id"])


def downgrade() -> None:
    op.drop_table("share_declines")
    op.drop_table("shares")
    op.drop_index("ix_sharing_purposes_status", table_name="sharing_purposes")
    op.drop_table("sharing_purposes")
