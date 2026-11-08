"""A Sharing Purpose may ask for a frozen Data Set (ADR 064, #467)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c5x6y7z8a9b0"
down_revision = "b4w5x6y7z8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sharing_purposes", sa.Column("data_set", sa.String(30)))
    op.add_column("sharing_purposes", sa.Column("data_set_since", sa.String(10)))
    op.add_column("sharing_purposes", sa.Column("data_set_domain", sa.String(20)))
    op.alter_column("shares", "document_id", nullable=True)
    op.add_column("shares", sa.Column("rows", JSONB))
    op.create_index(
        "uq_share_purpose_patient_data_set", "shares", ["sharing_purpose_id", "patient_id"],
        unique=True, postgresql_where=sa.text("document_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_share_purpose_patient_data_set", "shares")
    op.execute("DELETE FROM shares WHERE document_id IS NULL")
    op.drop_column("shares", "rows")
    op.alter_column("shares", "document_id", nullable=False)
    op.drop_column("sharing_purposes", "data_set_domain")
    op.drop_column("sharing_purposes", "data_set_since")
    op.drop_column("sharing_purposes", "data_set")
