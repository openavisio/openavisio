"""Mails speak the household's language and say who invites (ADR 054)."""

from sqlalchemy import select

from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User
from app.services.email import notify_settings, send_invitation_email
from tests.test_contentless_mail import _sent


async def _org(db, **kw) -> None:
    org = (await db.execute(select(Organization))).scalar_one_or_none()
    if not org:
        org = Organization(name="Familie Riedel")
        db.add(org)
    for k, v in kw.items():
        setattr(org, k, v)
    await db.commit()


async def test_a_german_household_gets_a_german_invitation_naming_who_invites(monkeypatch, db):
    await _org(db, name="Familie Riedel", default_language="de")
    u = User(email="mama@t.com", hashed_password=hash_password("Pass1!"), role="admin", is_active=True,
             first_name="Anna", last_name="Riedel")
    db.add(u)
    await db.commit()
    mails = await _sent(monkeypatch, db, lambda: send_invitation_email("oma@t.com", "tok", str(u.id)))
    subject, html, text = mails[0]
    assert subject == "Anna Riedel lädt dich zu OpenAvisio ein"
    assert "„Familie Riedel“" in text and "Die Einladung gilt 7 Tage." in text
    assert 'lang="de"' in html


async def test_a_household_member_gets_no_second_mail_after_the_invitation(db):
    await _org(db, is_household=True)
    assert (await notify_settings(db))["caregiver_added"] is False
    await _org(db, is_household=False)
    assert (await notify_settings(db))["caregiver_added"] is True
