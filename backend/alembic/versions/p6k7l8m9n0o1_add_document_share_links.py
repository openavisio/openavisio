"""add document share links (document_share_links, document_share_link_items)

Revision ID: p6k7l8m9n0o1
Revises: o5j6k7l8m9n0
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "p6k7l8m9n0o1"
down_revision = "o5j6k7l8m9n0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_share_links",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("patient_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_legal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_document_share_links_token_hash"),
    )
    op.create_index("ix_document_share_links_patient_id", "document_share_links", ["patient_id"])
    op.create_index("ix_document_share_links_token_hash", "document_share_links", ["token_hash"])
    op.create_index("ix_document_share_links_status", "document_share_links", ["status"])

    op.create_table(
        "document_share_link_items",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("share_link_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["share_link_id"], ["document_share_links.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["document_references.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_link_id", "document_id", name="uq_share_link_document"),
    )
    op.create_index("ix_document_share_link_items_share_link_id", "document_share_link_items", ["share_link_id"])
    op.create_index("ix_document_share_link_items_document_id", "document_share_link_items", ["document_id"])
    op.create_index("ix_document_share_link_items_patient_id", "document_share_link_items", ["patient_id"])


def downgrade() -> None:
    op.drop_table("document_share_link_items")
    op.drop_index("ix_document_share_links_status", table_name="document_share_links")
    op.drop_index("ix_document_share_links_token_hash", table_name="document_share_links")
    op.drop_index("ix_document_share_links_patient_id", table_name="document_share_links")
    op.drop_table("document_share_links")
