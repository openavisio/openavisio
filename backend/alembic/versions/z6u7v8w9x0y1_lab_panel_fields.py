"""lab panel + reference range fields on observations (#69)"""

import sqlalchemy as sa
from alembic import op

revision = "z6u7v8w9x0y1"
down_revision = "y5t6u7v8w9x0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("observations", sa.Column("panel", sa.String(length=128), nullable=True))
    op.add_column("observations", sa.Column("reference_range", sa.String(length=100), nullable=True))
    op.add_column("observations", sa.Column("ref_low", sa.Float(), nullable=True))
    op.add_column("observations", sa.Column("ref_high", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("observations", "ref_high")
    op.drop_column("observations", "ref_low")
    op.drop_column("observations", "reference_range")
    op.drop_column("observations", "panel")
