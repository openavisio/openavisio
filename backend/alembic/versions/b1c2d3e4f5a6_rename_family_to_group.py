"""rename family to group

Revision ID: b1c2d3e4f5a6
Revises: ea27601363a6
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'ea27601363a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename tables
    op.rename_table('families', 'groups')
    op.rename_table('family_memberships', 'group_memberships')
    op.rename_table('family_invite_tokens', 'group_invite_tokens')

    # Rename family_id → group_id in group_memberships
    op.alter_column('group_memberships', 'family_id', new_column_name='group_id')

    # Rename family_id → group_id in group_invite_tokens
    op.alter_column('group_invite_tokens', 'family_id', new_column_name='group_id')

    # Rename family_id → group_id in patients
    op.alter_column('patients', 'family_id', new_column_name='group_id')

    # Rename indexes
    op.execute('ALTER INDEX ix_family_memberships_family_id RENAME TO ix_group_memberships_group_id')
    op.execute('ALTER INDEX ix_family_memberships_user_id RENAME TO ix_group_memberships_user_id')
    op.execute('ALTER INDEX ix_family_invite_tokens_family_id RENAME TO ix_group_invite_tokens_group_id')
    op.execute('ALTER INDEX ix_family_invite_tokens_token RENAME TO ix_group_invite_tokens_token')


def downgrade() -> None:
    # Rename indexes back
    op.execute('ALTER INDEX ix_group_memberships_group_id RENAME TO ix_family_memberships_family_id')
    op.execute('ALTER INDEX ix_group_memberships_user_id RENAME TO ix_family_memberships_user_id')
    op.execute('ALTER INDEX ix_group_invite_tokens_group_id RENAME TO ix_family_invite_tokens_family_id')
    op.execute('ALTER INDEX ix_group_invite_tokens_token RENAME TO ix_family_invite_tokens_token')

    # Rename group_id → family_id in patients
    op.alter_column('patients', 'group_id', new_column_name='family_id')

    # Rename group_id → family_id in group_invite_tokens
    op.alter_column('group_invite_tokens', 'group_id', new_column_name='family_id')

    # Rename group_id → family_id in group_memberships
    op.alter_column('group_memberships', 'group_id', new_column_name='family_id')

    # Rename tables back
    op.rename_table('group_invite_tokens', 'family_invite_tokens')
    op.rename_table('group_memberships', 'family_memberships')
    op.rename_table('groups', 'families')
