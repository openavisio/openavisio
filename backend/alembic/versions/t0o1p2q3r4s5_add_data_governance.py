"""add data governance tables: data_categories, consent_records (#15/#16)

Revision ID: t0o1p2q3r4s5
Revises: r8m9n0o1p2q3
Create Date: 2026-07-02

NOTE ON ORDERING: this descends from r8m9n0o1p2q3 (task-run tracking, PR #29),
which descends from the merge migration s9n0o1p2q3r4 (PR #30). Merge PRs #30 and
#29 before this one so the Alembic history stays a single linear head.

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "t0o1p2q3r4s5"
down_revision = "r8m9n0o1p2q3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_categories",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("lawful_basis", sa.String(50), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_data_categories_code"),
    )
    op.create_index("ix_data_categories_code", "data_categories", ["code"])

    op.create_table(
        "consent_records",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("policy_version", sa.String(20), nullable=False, server_default="1"),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])


def downgrade() -> None:
    op.drop_table("consent_records")
    op.drop_index("ix_data_categories_code", table_name="data_categories")
    op.drop_table("data_categories")
