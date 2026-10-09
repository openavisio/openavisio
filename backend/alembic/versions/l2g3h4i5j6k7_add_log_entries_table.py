"""add log_entries table

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-06-06

"""
from alembic import op
import sqlalchemy as sa

revision = "l2g3h4i5j6k7"
down_revision = "k1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "log_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("logger", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exc", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_log_entries_level", "log_entries", ["level"])
    op.create_index("ix_log_entries_source", "log_entries", ["source"])
    op.create_index("ix_log_entries_timestamp", "log_entries", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_log_entries_timestamp", table_name="log_entries")
    op.drop_index("ix_log_entries_source", table_name="log_entries")
    op.drop_index("ix_log_entries_level", table_name="log_entries")
    op.drop_table("log_entries")
