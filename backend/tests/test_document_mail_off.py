"""No mail per processed document unless switched on (#329)."""

import app.services.email as email
from app.models.system import SystemSetting


async def test_the_document_mail_is_off_until_switched_on(db):
    assert await email._document_mail_on(db) is False
    db.add(SystemSetting(key="notify.document_processed", value="true"))
    await db.commit()
    assert await email._document_mail_on(db) is True


async def test_off_stops_before_anything_is_read(monkeypatch):
    reached = []
    async def smtp(_db):
        return {"from_address": "x@t.com"}
    async def off(_db):
        return False
    async def include_content(_db):
        reached.append(True)
        return False
    monkeypatch.setattr(email, "_get_smtp_config", smtp)
    monkeypatch.setattr(email, "_document_mail_on", off)
    monkeypatch.setattr(email, "_include_content", include_content)
    await email.send_document_processed_notification("00000000-0000-0000-0000-000000000000")
    assert reached == []
