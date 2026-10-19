"""No mail per processed document unless switched on (ADR 054)."""

import app.services.email as email
from app.models.system import SystemSetting


async def test_the_document_mail_is_off_until_switched_on(db):
    assert (await email.notify_settings(db))["document_processed"] is False
    db.add(SystemSetting(key="notify.document_processed", value="true"))
    await db.commit()
    assert (await email.notify_settings(db))["document_processed"] is True


async def test_off_stops_before_the_document_is_read(monkeypatch):
    reached = []
    async def smtp(_db):
        return {"from_address": "x@t.com"}
    async def off(_db):
        return {"document_processed": False}
    async def org(_db):
        reached.append(True)
        return "en", ""
    monkeypatch.setattr(email, "_get_smtp_config", smtp)
    monkeypatch.setattr(email, "notify_settings", off)
    monkeypatch.setattr(email, "_org", org)
    await email.send_document_processed_notification("00000000-0000-0000-0000-000000000000")
    assert reached == []
