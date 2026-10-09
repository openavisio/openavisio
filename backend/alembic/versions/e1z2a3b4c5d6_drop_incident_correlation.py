"""drop the dormant incident correlation columns (#119)

Nothing ever wrote or read them. They were a pre-built home for exactly the
feature docs/regulatory-positioning.md rules out: software-inferred correlation
between seizures and medication, confidence score included. Dead schema is an
invitation — this removes it. Re-adding requires a formal MDR assessment first.
"""

import sqlalchemy as sa
from alembic import op

revision = "e1z2a3b4c5d6"
down_revision = "d0y1z2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("incidents", "correlation_analyzed")
    op.drop_column("incidents", "correlated_medications")
    op.drop_column("incidents", "correlation_patterns")
    op.drop_column("incidents", "correlation_confidence")


def downgrade() -> None:
    op.add_column("incidents", sa.Column("correlation_analyzed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("incidents", sa.Column("correlated_medications", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("correlation_patterns", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("correlation_confidence", sa.Float(), nullable=True))
