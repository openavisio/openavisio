"""merged_into_id: a merged-away condition points at its survivor (#159)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "g3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conditions", sa.Column("merged_into_id", UUID(as_uuid=True), sa.ForeignKey("conditions.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("conditions", "merged_into_id")
