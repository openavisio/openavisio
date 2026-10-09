"""add task_runs table (Celery task tracking, issue #4)

Revision ID: r8m9n0o1p2q3
Revises: s9n0o1p2q3r4
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "r8m9n0o1p2q3"
down_revision = "s9n0o1p2q3r4"  # reparented onto the merge head (PR #30)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_runs",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.String(155), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("args_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_task_runs_task_id"),
    )
    op.create_index("ix_task_runs_task_id", "task_runs", ["task_id"])
    op.create_index("ix_task_runs_task_name", "task_runs", ["task_name"])
    op.create_index("ix_task_runs_status", "task_runs", ["status"])
    op.create_index("ix_task_runs_created_at", "task_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_task_runs_created_at", table_name="task_runs")
    op.drop_index("ix_task_runs_status", table_name="task_runs")
    op.drop_index("ix_task_runs_task_name", table_name="task_runs")
    op.drop_index("ix_task_runs_task_id", table_name="task_runs")
    op.drop_table("task_runs")
