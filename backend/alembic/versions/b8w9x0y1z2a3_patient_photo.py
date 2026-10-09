"""optional patient photo (encrypted PHI, ADR-031)"""

import sqlalchemy as sa
from alembic import op

revision = "b8w9x0y1z2a3"
down_revision = "a7v8w9x0y1z2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("photo_storage_path", sa.String(length=1024), nullable=True))
    op.add_column("patients", sa.Column("photo_dek", sa.LargeBinary(), nullable=True))
    op.add_column("patients", sa.Column("photo_content_type", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "photo_content_type")
    op.drop_column("patients", "photo_dek")
    op.drop_column("patients", "photo_storage_path")
