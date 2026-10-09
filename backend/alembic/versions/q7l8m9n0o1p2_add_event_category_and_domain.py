"""add category + developmental_domain to calendar_events (milestones, issue #11)

Revision ID: q7l8m9n0o1p2
Revises: o5j6k7l8m9n0
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa

revision = "q7l8m9n0o1p2"
down_revision = "o5j6k7l8m9n0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calendar_events",
        sa.Column("category", sa.String(20), nullable=False, server_default="appointment"),
    )
    op.add_column(
        "calendar_events",
        sa.Column("developmental_domain", sa.String(20), nullable=True),
    )
    op.create_index("ix_calendar_events_category", "calendar_events", ["category"])


def downgrade() -> None:
    op.drop_index("ix_calendar_events_category", table_name="calendar_events")
    op.drop_column("calendar_events", "developmental_domain")
    op.drop_column("calendar_events", "category")
