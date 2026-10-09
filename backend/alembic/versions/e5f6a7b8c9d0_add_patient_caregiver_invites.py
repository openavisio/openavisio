"""add patient_caregiver_invites

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'patient_caregiver_invites' not in inspector.get_table_names():
        op.create_table(
            'patient_caregiver_invites',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('patient_id', UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
            sa.Column('invited_email', sa.String(256), nullable=True),
            sa.Column('access_level', sa.String(50), nullable=False, server_default='view'),
            sa.Column('invited_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('token', sa.String(256), nullable=False, unique=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_used', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        )
        op.create_index('ix_patient_caregiver_invites_token', 'patient_caregiver_invites', ['token'], unique=True)
        op.create_index('ix_patient_caregiver_invites_patient_id', 'patient_caregiver_invites', ['patient_id'])


def downgrade() -> None:
    op.drop_index('ix_patient_caregiver_invites_patient_id', table_name='patient_caregiver_invites')
    op.drop_index('ix_patient_caregiver_invites_token', table_name='patient_caregiver_invites')
    op.drop_table('patient_caregiver_invites')
