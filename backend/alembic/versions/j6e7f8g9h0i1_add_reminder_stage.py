"""staged reminders for deadline events (ADR 041)"""

import sqlalchemy as sa
from alembic import op

revision = "j6e7f8g9h0i1"
down_revision = "i5d6e7f8g9h0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A Widerspruch deadline is reminded twice (14 and 3 days), so reminder_sent_at
    # alone no longer says how far along an event is.
    op.add_column(
        "calendar_events",
        sa.Column("reminder_stage", sa.Integer(), nullable=False, server_default="0"),
    )
    # Existing events that already had their single reminder are done, not pending.
    op.execute("UPDATE calendar_events SET reminder_stage = 2 WHERE reminder_sent_at IS NOT NULL")


def downgrade() -> None:
    op.drop_column("calendar_events", "reminder_stage")
