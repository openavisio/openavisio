"""rename date to issued_date on document_references

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'document_references',
        'date',
        new_column_name='issued_date',
        existing_type=sa.String(50),
        type_=sa.Date(),
        existing_nullable=True,
        postgresql_using='date::date',
    )


def downgrade() -> None:
    op.alter_column(
        'document_references',
        'issued_date',
        new_column_name='date',
        existing_type=sa.Date(),
        type_=sa.String(50),
        existing_nullable=True,
        postgresql_using='issued_date::text',
    )
