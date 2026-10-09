"""merge legal representation into the grant (ADR 027): add flag, backfill, drop rep tables"""

import sqlalchemy as sa
from alembic import op

revision = "w3r4s5t6u7v8"
down_revision = "v2q3r4s5t6u7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patient_access", sa.Column(
        "is_legal_representative", sa.Boolean(), nullable=False, server_default=sa.false()))

    # Backfill: every active representation with a linked user becomes a legal-rep grant.
    # If the user already has an active grant, just flag it; otherwise create a full grant.
    op.execute("""
        UPDATE patient_access pa SET is_legal_representative = true
        FROM patient_representations pr
        WHERE pr.user_id = pa.user_id AND pr.patient_id = pa.patient_id
          AND pr.status = 'active' AND pr.is_deleted = false
          AND pa.revoked_at IS NULL AND pa.is_deleted = false
    """)
    op.execute("""
        INSERT INTO patient_access (id, patient_id, user_id, access_level, granted_by_user_id,
                                    granted_at, is_legal_representative, created_at, updated_at, is_deleted)
        SELECT gen_random_uuid(), pr.patient_id, pr.user_id, 'full', pr.user_id,
               now(), true, now(), now(), false
        FROM patient_representations pr
        WHERE pr.user_id IS NOT NULL AND pr.status = 'active' AND pr.is_deleted = false
          AND NOT EXISTS (
            SELECT 1 FROM patient_access pa
            WHERE pa.patient_id = pr.patient_id AND pa.user_id = pr.user_id
              AND pa.revoked_at IS NULL AND pa.is_deleted = false
          )
    """)

    op.drop_table("representation_invite_tokens")
    op.drop_table("patient_representations")


def downgrade() -> None:
    op.drop_column("patient_access", "is_legal_representative")
    # rep tables are not recreated on downgrade
