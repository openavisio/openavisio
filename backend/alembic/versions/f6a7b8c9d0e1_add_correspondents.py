"""add correspondents

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'correspondents' not in existing_tables:
        op.create_table(
            'correspondents',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('name', sa.String(256), nullable=False),
            sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organization.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        )
        op.create_index('ix_correspondents_organization_id', 'correspondents', ['organization_id'])

    doc_columns = {c['name'] for c in inspector.get_columns('document_references')}
    if 'correspondent_id' not in doc_columns:
        op.add_column(
            'document_references',
            sa.Column('correspondent_id', UUID(as_uuid=True), sa.ForeignKey('correspondents.id'), nullable=True),
        )


def downgrade() -> None:
    op.drop_column('document_references', 'correspondent_id')
    op.drop_index('ix_correspondents_organization_id', table_name='correspondents')
    op.drop_table('correspondents')
