"""A group invitation carries the role it was sent with"""

import sqlalchemy as sa
from alembic import op

revision = "t6o7p8q9r0s1"
down_revision = "s5n6o7p8q9r0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_invite_tokens", sa.Column("role", sa.String(50), nullable=False, server_default="viewer"))


def downgrade() -> None:
    op.drop_column("group_invite_tokens", "role")
