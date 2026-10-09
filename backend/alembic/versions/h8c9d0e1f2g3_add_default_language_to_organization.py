"""add default_language to organization

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'h8c9d0e1f2g3'
down_revision: Union[str, Sequence[str], None] = 'g7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("organization")]
    if "default_language" not in columns:
        op.add_column("organization", sa.Column("default_language", sa.String(10), nullable=True, server_default="en"))


def downgrade() -> None:
    op.drop_column("organization", "default_language")
