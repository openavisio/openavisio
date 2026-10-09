"""ownership retired: backfill admin grants, rename patients.owner_id to created_by (ADR 026)"""

import sqlalchemy as sa
from alembic import op

revision = "v2q3r4s5t6u7"
down_revision = "u1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO patient_access (id, patient_id, user_id, access_level, granted_by_user_id, granted_at, created_at, updated_at, is_deleted)
        SELECT gen_random_uuid(), p.id, p.owner_id, 'admin', p.owner_id, now(), now(), now(), false
        FROM patients p
        WHERE p.is_deleted = false
          AND NOT EXISTS (
            SELECT 1 FROM patient_access pa
            WHERE pa.patient_id = p.id AND pa.user_id = p.owner_id
              AND pa.access_level = 'admin' AND pa.revoked_at IS NULL
          )
    """)
    op.alter_column("patients", "owner_id", new_column_name="created_by")


def downgrade() -> None:
    op.alter_column("patients", "created_by", new_column_name="owner_id")
