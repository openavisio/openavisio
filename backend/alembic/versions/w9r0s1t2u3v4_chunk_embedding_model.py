"""Which model embedded a chunk, so a model change is detectable (#238)"""

import sqlalchemy as sa
from alembic import op

revision = "w9r0s1t2u3v4"
down_revision = "v8q9r0s1t2u3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("embedding_model", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding_model")
