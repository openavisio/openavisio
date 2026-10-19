"""#251: notification mails carry no health data unless an admin turns it on."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.system import SystemSetting
from app.models.user import User
from app.services.email import _contentless, notify_settings


async def _admin(client: AsyncClient, db: AsyncSession) -> dict:
    db.add(User(email="mailadmin@t.com", hashed_password=hash_password("Pass1!"), role="admin",
                is_active=True, first_name="A", last_name="Admin"))
    await db.commit()
    r = await client.post("/api/auth/login", json={"email": "mailadmin@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_content_is_off_until_an_admin_turns_it_on(client: AsyncClient, db: AsyncSession):
    assert (await notify_settings(db))["include_content"] is False
    h = await _admin(client, db)
    r = await client.get("/api/admin/notification-settings", headers=h)
    assert r.json() == {"event_reminder": True, "caregiver_added": True, "invitation": True, "include_content": False,
                         "document_processed": False}

    r = await client.put("/api/admin/notification-settings", headers=h, json={"include_content": True})
    assert r.json()["include_content"] is True and r.json()["event_reminder"] is True
    assert (await notify_settings(db))["include_content"] is True


async def test_anything_but_true_keeps_content_out(db: AsyncSession):
    db.add(SystemSetting(key="notify.include_content", value="yes"))
    await db.commit()
    assert (await notify_settings(db))["include_content"] is False


async def _sent(monkeypatch, db, send) -> list[tuple[str, str, str]]:
    """Run a sender against the test session and catch what it would mail."""
    import contextlib
    from app.core import database
    from app.services import email

    @contextlib.asynccontextmanager
    async def session():
        yield db

    async def smtp(_db):
        return {"host": "x", "port": 25, "user": None, "password": None, "from_address": "x@x"}

    out = []
    monkeypatch.setattr(database, "AsyncSessionLocal", session)
    monkeypatch.setattr(email, "_get_smtp_config", smtp)
    monkeypatch.setattr(email, "_send_smtp", lambda _cfg, _to, subject, html, text: out.append((subject, html, text)))
    await send()
    return out


async def test_reminders_and_access_mails_name_no_patient_unless_turned_on(monkeypatch, db: AsyncSession):
    from datetime import UTC, date, datetime, timedelta
    from app.models.access import PatientAccess
    from app.models.calendar import CalendarEvent
    from app.models.patient import Patient
    from app.services.email import send_caregiver_added_notification, send_event_reminder

    u = User(email="carer@t.com", hashed_password=hash_password("Pass1!"), role="user",
             is_active=True, first_name="C", last_name="Carer")
    db.add(u)
    await db.commit()
    p = Patient(given_name="Lena", family_name="Geheim", birth_date="2019-05-14", created_by=u.id)
    db.add(p)
    await db.commit()
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin", granted_at=datetime.now(UTC)))
    e = CalendarEvent(patient_id=p.id, owner_id=u.id, title="Widerspruch Kassenbescheid", category="deadline",
                      start_at=(date.today() + timedelta(days=5)).isoformat())
    db.add(e)
    await db.commit()

    async def both():
        await send_event_reminder(str(e.id))
        await send_caregiver_added_notification(str(p.id), str(u.id))

    mails = await _sent(monkeypatch, db, both)
    assert len(mails) == 2
    for subject, html, text in mails:
        assert subject.startswith("OpenAvisio: ")
        for secret in ("Geheim", "Widerspruch"):
            assert secret not in subject + html + text

    db.add(SystemSetting(key="notify.include_content", value="true"))
    await db.commit()
    mails = await _sent(monkeypatch, db, both)
    assert len(mails) == 2 and all("Geheim" in html for _, html, _ in mails)


def test_the_contentless_mail_names_the_occasion_and_the_link():
    url = "https://app.example/patients/1b2c/documents/3d4e"
    subject, html, text = _contentless(url, "en", "document")
    assert subject == "OpenAvisio: a document is ready"
    assert url in text and url in html
    assert "Log in" in text
    subject, html, text = _contentless(None, "de", "deadline", "in 5 Tagen")
    assert subject == "OpenAvisio: Eine Frist endet in 5 Tagen"
    assert "href" not in html and "None" not in text
