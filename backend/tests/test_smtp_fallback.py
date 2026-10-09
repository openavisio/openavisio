"""SMTP falls back to the environment when the database has no settings (#249).

A hosted installation is handed over ready to send. Without this the operator
would have to write into the customer's database to configure mail, which is
exactly what the hosted setup promises not to do.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import encrypt_setting
from app.models.system import SystemSetting
from app.services.email import _get_smtp_config


async def test_no_db_rows_and_no_env_means_no_mail(db: AsyncSession):
    settings.smtp_host = ""
    assert await _get_smtp_config(db) is None


async def test_env_is_used_when_the_database_is_empty(db: AsyncSession):
    settings.smtp_host = "mail.example.org"
    settings.smtp_port = 465
    settings.smtp_user = "instance-42"
    settings.smtp_password = "env-secret"
    settings.smtp_from = "noreply@avisiohub.cloud"
    try:
        cfg = await _get_smtp_config(db)
        assert cfg == {
            "host": "mail.example.org",
            "port": 465,
            "user": "instance-42",
            "password": "env-secret",
            "from_address": "noreply@avisiohub.cloud",
        }
    finally:
        settings.smtp_host = ""


async def test_database_wins_over_the_environment(db: AsyncSession):
    """The customer configuring SMTP in the admin UI must override provisioning."""
    settings.smtp_host = "mail.example.org"
    settings.smtp_user = "instance-42"
    settings.smtp_password = "env-secret"
    db.add_all([
        SystemSetting(key="smtp.host", value="own.mailserver.de"),
        SystemSetting(key="smtp.port", value="2525"),
        SystemSetting(key="smtp.user", value="familie"),
        SystemSetting(key="smtp.password", value=encrypt_setting("db-secret")),
    ])
    await db.commit()
    try:
        cfg = await _get_smtp_config(db)
        assert cfg["host"] == "own.mailserver.de"
        assert cfg["port"] == 2525
        assert cfg["password"] == "db-secret"
        # No smtp.from row: falls back to the user, not to the env sender
        assert cfg["from_address"] == "familie"
    finally:
        settings.smtp_host = ""
