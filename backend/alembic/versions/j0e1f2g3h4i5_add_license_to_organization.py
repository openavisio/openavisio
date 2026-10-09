"""add license to organization

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-06-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'j0e1f2g3h4i5'
down_revision: Union[str, Sequence[str], None] = 'i9d0e1f2g3h4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('organization')]
    if 'license_token' not in columns:
        op.add_column('organization', sa.Column('license_token', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('organization', 'license_token')
