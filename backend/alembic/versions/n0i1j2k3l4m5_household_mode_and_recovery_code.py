"""household mode on the organization, recovery code on the user (ADR 044, ADR 046)"""

import sqlalchemy as sa
from alembic import op

revision = "n0i1j2k3l4m5"
down_revision = "m9h0i1j2k3l4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization",
        sa.Column("is_household", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("recovery_code_hash", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "recovery_code_hash")
    op.drop_column("organization", "is_household")
