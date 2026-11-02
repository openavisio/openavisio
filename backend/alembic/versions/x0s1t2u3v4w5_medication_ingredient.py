"""The active ingredient of a medication, so the chat finds a brand by its substance (#209)"""

import sqlalchemy as sa
from alembic import op

revision = "x0s1t2u3v4w5"
down_revision = "w9r0s1t2u3v4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medication_statements", sa.Column("ingredient", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("medication_statements", "ingredient")
