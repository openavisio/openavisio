"""encrypt secret system settings at rest

Revision ID: x4s5t6u7v8w9
Revises: w3r4s5t6u7v8
Create Date: 2026-07-07

Encrypts existing plaintext secret settings (smtp.password, ai.api_key) under
the envelope KEK. Idempotent: values already carrying the enc:v1: prefix are
skipped. Requires DOCUMENT_ENCRYPTION_KEY to be set (same invariant as document
encryption). Downgrade decrypts back to plaintext.
"""
from alembic import op
import sqlalchemy as sa

from app.core.encryption import encrypt_setting, decrypt_setting

revision = "x4s5t6u7v8w9"
down_revision = "w3r4s5t6u7v8"
branch_labels = None
depends_on = None

_SECRET_KEYS = ("smtp.password", "ai.api_key")
_PREFIX = "enc:v1:"


def _rows(conn):
    return conn.execute(
        sa.text(
            "SELECT key, value FROM system_settings "
            "WHERE key = ANY(:keys) AND value IS NOT NULL"
        ),
        {"keys": list(_SECRET_KEYS)},
    ).fetchall()


def upgrade() -> None:
    conn = op.get_bind()
    for key, value in _rows(conn):
        if value.startswith(_PREFIX):
            continue
        conn.execute(
            sa.text("UPDATE system_settings SET value = :v WHERE key = :k"),
            {"v": encrypt_setting(value), "k": key},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for key, value in _rows(conn):
        if not value.startswith(_PREFIX):
            continue
        conn.execute(
            sa.text("UPDATE system_settings SET value = :v WHERE key = :k"),
            {"v": decrypt_setting(value), "k": key},
        )
