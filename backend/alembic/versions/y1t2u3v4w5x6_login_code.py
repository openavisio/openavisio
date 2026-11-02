"""A one-time code by mail when a password sign-in comes from a new device (#338)"""

import sqlalchemy as sa
from alembic import op

revision = "y1t2u3v4w5x6"
down_revision = "x0s1t2u3v4w5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("login_code_hash", sa.String(256), nullable=True))
    op.add_column("users", sa.Column("login_code_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "login_code_expires_at")
    op.drop_column("users", "login_code_hash")
