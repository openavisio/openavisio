"""add passkey credentials

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'i9d0e1f2g3h4'
down_revision: Union[str, Sequence[str], None] = 'h8c9d0e1f2g3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'passkey_credentials' not in existing_tables:
        op.create_table(
            'passkey_credentials',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('credential_id', sa.LargeBinary(), nullable=False),
            sa.Column('public_key', sa.LargeBinary(), nullable=False),
            sa.Column('sign_count', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('aaguid', sa.String(40), nullable=True),
            sa.Column('transports', sa.String(255), nullable=True),
            sa.Column('label', sa.String(100), nullable=False, server_default='Passkey'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_passkey_credentials_user_id', 'passkey_credentials', ['user_id'])
        op.create_index('ix_passkey_credentials_credential_id', 'passkey_credentials', ['credential_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_passkey_credentials_credential_id', table_name='passkey_credentials')
    op.drop_index('ix_passkey_credentials_user_id', table_name='passkey_credentials')
    op.drop_table('passkey_credentials')
