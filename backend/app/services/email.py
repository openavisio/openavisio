"""Transactional email service — reads SMTP config from SystemSetting at send time."""

import asyncio
import logging
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape  # the local `html` variable in each sender shadows the module

logger = logging.getLogger("openavisio.email")


async def _get_smtp_config(db) -> dict | None:
    from sqlalchemy import select
    from app.core.encryption import decrypt_setting
    from app.models.system import SystemSetting

    keys = ["smtp.host", "smtp.port", "smtp.user", "smtp.password", "smtp.from"]
    result = await db.execute(select(SystemSetting).where(SystemSetting.key.in_(keys)))
    cfg = {s.key: s.value for s in result.scalars().all()}

    host = cfg.get("smtp.host")
    if not host:
        # Hosted Deployments are provisioned sendable via .env; the customer can
        # still override in the admin UI, and the DB rows win once they exist (#249).
        from app.core.config import settings

        if not settings.smtp_host:
            return None
        return {
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "user": settings.smtp_user,
            "password": settings.smtp_password,
            "from_address": settings.smtp_from or settings.smtp_user or "noreply@openavisio.app",
        }

    return {
        "host": host,
        "port": int(cfg.get("smtp.port") or "587"),
        "user": cfg.get("smtp.user"),
        "password": decrypt_setting(cfg.get("smtp.password")),
        "from_address": cfg.get("smtp.from") or cfg.get("smtp.user") or "noreply@openavisio.app",
    }


def _send_smtp(smtp_cfg: dict, to_email: str, subject: str, html: str, text: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_cfg["from_address"]
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=15) as s:
        s.ehlo()
        try:
            s.starttls()
            s.ehlo()
        except smtplib.SMTPNotSupportedError:
            pass
        if smtp_cfg["user"] and smtp_cfg["password"]:
            s.login(smtp_cfg["user"], smtp_cfg["password"])
        s.sendmail(smtp_cfg["from_address"], [to_email], msg.as_string())



# ---------------------------------------------------------------------------
# Notification settings and language (ADR 054)
# ---------------------------------------------------------------------------

# field -> default; stored as SystemSetting notify.<field>
NOTIFY_DEFAULTS = {
    "event_reminder": True,
    "caregiver_added": True,
    "invitation": True,
    "include_content": False,  # #251: no health data in mails unless an admin decides so
    "document_processed": False,  # nobody asked for a mail per upload
}


async def notify_settings(db) -> dict[str, bool]:
    """Only the literal "true" switches a mail on; a household's member already got the invitation."""
    from sqlalchemy import select
    from app.models.organization import Organization
    from app.models.system import SystemSetting

    rows = await db.execute(select(SystemSetting).where(SystemSetting.key.in_([f"notify.{f}" for f in NOTIFY_DEFAULTS])))
    stored = {s.key: s.value for s in rows.scalars().all()}
    defaults = {**NOTIFY_DEFAULTS, "caregiver_added": not await db.scalar(select(Organization.is_household))}
    return {f: (stored.get(f"notify.{f}") or str(d)).lower() == "true" for f, d in defaults.items()}


async def _org(db) -> tuple[str, str]:
    """(language, name) of the Deployment; every mail speaks the household's language."""
    from sqlalchemy import select
    from app.models.organization import Organization

    org = (await db.execute(select(Organization))).scalar_one_or_none()
    return ("de" if org and org.default_language == "de" else "en"), (org.name if org else "")


_T = {
    "en": {
        "footer": "OpenAvisio automated notification",
        "open": "Open OpenAvisio",
        "document": ("OpenAvisio: a document is ready", "A document has been processed. Log in to see it."),
        "event": ("OpenAvisio: an appointment tomorrow", "There is an appointment tomorrow. Log in to see it."),
        "deadline": ("OpenAvisio: a deadline ends {when}", "A deadline ends {when}. Log in to see it."),
        "caregiver": ("OpenAvisio: you have access to a record", "You have been given access to a record. Log in to see it."),
        "doc_subject": "Document processed: {doc}",
        "doc_title": "Document processed",
        "doc_line": "A document has been processed for {patient}.",
        "doc_labels": ("Document", "Issued", "From"),
        "doc_button": "View document",
        "doc_unnamed": "Unnamed document",
        "care_subject": "You have been added as a caregiver for {patient}",
        "care_title": "Caregiver access granted",
        "care_line": "You have been granted access to the patient record for {patient} in OpenAvisio.",
        "care_button": "View patient",
        "inv_subject": "{inviter} invited you to OpenAvisio",
        "inv_line": '{inviter} invited you to join "{org}" in OpenAvisio.',
        "inv_here": "Create your account here: {url}",
        "inv_nolink": "Ask the person who invited you for the registration link.",
        "inv_expires": "This invitation expires in 7 days.",
        "inv_button": "Create account",
        "someone": "Someone",
        "for": "for",
        "days": ("soon", "today", "tomorrow", "in {n} days"),
        "dl_subject": "Deadline {when}: {title}",
        "ev_subject": "Reminder: {title} tomorrow",
        "dl_line": "Deadline: '{title}' for {patient} expires {when}.",
        "ev_line": "Reminder: '{title}' for {patient} is scheduled in approximately 24 hours.",
        "dl_title": "Deadline",
        "ev_title": "Reminder",
        "ev_labels": ("When", "Where", "Provider"),
        "advice": "This date was calculated from the decision letter and is not legal advice. "
                  "If in doubt, object early or seek advice. Objecting too early costs nothing.",
        "cal_button": "View calendar",
    },
    "de": {
        "footer": "Automatische Benachrichtigung von OpenAvisio",
        "open": "OpenAvisio öffnen",
        "document": ("OpenAvisio: Ein Dokument ist fertig", "Ein Dokument ist fertig verarbeitet. Melde dich an, um es zu sehen."),
        "event": ("OpenAvisio: Morgen steht ein Termin an", "Morgen steht ein Termin an. Melde dich an, um ihn zu sehen."),
        "deadline": ("OpenAvisio: Eine Frist endet {when}", "Eine Frist endet {when}. Melde dich an, um sie zu sehen."),
        "caregiver": ("OpenAvisio: Du hast Zugriff auf eine Akte", "Du hast Zugriff auf eine Akte bekommen. Melde dich an, um sie zu sehen."),
        "doc_subject": "Dokument verarbeitet: {doc}",
        "doc_title": "Dokument verarbeitet",
        "doc_line": "Für {patient} wurde ein Dokument verarbeitet.",
        "doc_labels": ("Dokument", "Datum", "Von"),
        "doc_button": "Dokument ansehen",
        "doc_unnamed": "Dokument ohne Namen",
        "care_subject": "Du hast Zugriff auf die Akte von {patient}",
        "care_title": "Zugriff erteilt",
        "care_line": "Du hast in OpenAvisio Zugriff auf die Akte von {patient} bekommen.",
        "care_button": "Akte öffnen",
        "inv_subject": "{inviter} lädt dich zu OpenAvisio ein",
        "inv_line": "{inviter} hat dich zu „{org}“ in OpenAvisio eingeladen.",
        "inv_here": "Hier legst du dein Konto an: {url}",
        "inv_nolink": "Den Link zur Anmeldung bekommst du von der Person, die dich eingeladen hat.",
        "inv_expires": "Die Einladung gilt 7 Tage.",
        "inv_button": "Konto anlegen",
        "someone": "Jemand",
        "for": "für",
        "days": ("bald", "heute", "morgen", "in {n} Tagen"),
        "dl_subject": "Frist endet {when}: {title}",
        "ev_subject": "Erinnerung: {title} morgen",
        "dl_line": "Frist: „{title}“ für {patient} endet {when}.",
        "ev_line": "Erinnerung: „{title}“ für {patient} ist morgen.",
        "dl_title": "Frist",
        "ev_title": "Erinnerung",
        "ev_labels": ("Wann", "Wo", "Praxis"),
        "advice": "Dieses Datum wurde aus dem Bescheid berechnet und ist keine Rechtsberatung. "
                  "Im Zweifel früh widersprechen oder beraten lassen. Ein zu früher Widerspruch kostet nichts.",
        "cal_button": "Kalender öffnen",
    },
}


def _when(lang: str, days: int | None) -> str:
    soon, today, tomorrow, later = _T[lang]["days"]
    return soon if days is None else today if days == 0 else tomorrow if days == 1 else later.format(n=days)


def _button(url: str | None, label: str) -> str:
    return (
        f"<p><a href='{escape(url)}' style='display:inline-block;background:#2563eb;color:#fff;"
        f"padding:10px 20px;border-radius:6px;text-decoration:none;font-size:14px'>{escape(label)}</a></p>"
        if url else ""
    )


def _page(lang: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<body style="font-family:sans-serif;color:#111;max-width:580px;margin:0 auto;padding:24px">
{body}
  <p style="color:#9ca3af;font-size:11px;margin-top:32px">{_T[lang]["footer"]}</p>
</body>
</html>"""


def _contentless(url: str | None, lang: str, kind: str, when: str = "") -> tuple[str, str, str]:
    """(subject, html, text) naming the occasion and nothing else: no patient, title or finding (#251, ADR 054)."""
    subject, line = (s.format(when=when) for s in _T[lang][kind])
    text = "\n".join(filter(None, [line, "", url, "", _T[lang]["footer"]]))
    return subject, _page(lang, f"  <p>{escape(line)}</p>\n  {_button(url, _T[lang]['open'])}"), text


async def _get_caregivers_for_patient(db, patient_id: uuid.UUID):
    """Return active User objects with access to the given patient (owner + direct grants)."""
    from datetime import UTC, datetime
    from sqlalchemy import select
    from app.models.access import PatientAccess
    from app.models.patient import Patient
    from app.models.user import User

    patient = (await db.execute(select(Patient).where(Patient.id == patient_id))).scalar_one_or_none()
    if not patient:
        return [], None

    now = datetime.now(UTC)
    access_result = await db.execute(
        select(PatientAccess.user_id).where(
            PatientAccess.patient_id == patient_id,
            PatientAccess.revoked_at.is_(None),
            (PatientAccess.expires_at.is_(None)) | (PatientAccess.expires_at > now),
        )
    )
    recipient_ids = {row[0] for row in access_result}
    users_result = await db.execute(
        select(User).where(
            User.id.in_(recipient_ids),
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    return users_result.scalars().all(), patient


async def _send_all(smtp_cfg: dict, recipients, subject: str, html: str, text: str, what: str) -> None:
    loop = asyncio.get_event_loop()
    for to in recipients:
        try:
            await loop.run_in_executor(None, _send_smtp, smtp_cfg, to, subject, html, text)
            logger.info("%s sent to %s", what, to)
        except Exception as exc:
            logger.warning("Failed to send %s to %s: %s", what, to, exc)


# ---------------------------------------------------------------------------
# Document processed
# ---------------------------------------------------------------------------

async def send_document_processed_notification(doc_id: str) -> None:
    """Notify all caregivers with access to the patient that a document finished processing."""
    from sqlalchemy import select
    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from app.models.correspondent import Correspondent
    from app.models.document import DocumentReference

    try:
        async with AsyncSessionLocal() as db:
            smtp_cfg = await _get_smtp_config(db)
            if not smtp_cfg:
                return
            notify = await notify_settings(db)
            if not notify["document_processed"]:
                return
            lang, _ = await _org(db)
            doc = (await db.execute(select(DocumentReference).where(DocumentReference.id == uuid.UUID(doc_id)))).scalar_one_or_none()
            if not doc:
                return
            recipients, patient = await _get_caregivers_for_patient(db, doc.patient_id)
            correspondent = (
                await db.scalar(select(Correspondent.name).where(Correspondent.id == doc.correspondent_id))
                if doc.correspondent_id else None
            )

        if not recipients or not patient:
            return

        t = _T[lang]
        url = f"{settings.app_url}/patients/{doc.patient_id}/documents/{doc.id}" if settings.app_url else None
        if notify["include_content"]:
            patient_name = f"{patient.given_name} {patient.family_name}"
            doc_name = doc.file_name or doc.description or t["doc_unnamed"]
            issued = str(doc.issued_date) if doc.issued_date else "-"
            rows = [(label, v) for label, v in zip(t["doc_labels"], (doc_name, issued, correspondent)) if v]
            subject = t["doc_subject"].format(doc=doc_name)
            text = "\n".join([
                t["doc_line"].format(patient=patient_name), "",
                *(f"{label}: {v}" for label, v in rows),
                *(["", url] if url else []), "", t["footer"],
            ])
            html = _page(lang, f"""  <h2 style="font-size:17px;margin-bottom:2px">{t["doc_title"]}</h2>
  <p style="color:#6b7280;margin-top:0">{t["for"]} <strong>{escape(patient_name)}</strong></p>
  <table style="width:100%;border-collapse:collapse;margin:12px 0">{"".join(
      f"<tr><td style='padding:6px 0;color:#6b7280;width:110px'>{label}</td><td style='padding:6px 0'>{escape(v)}</td></tr>"
      for label, v in rows)}</table>
  {_button(url, t["doc_button"])}""")
        else:
            subject, html, text = _contentless(url, lang, "document")

        await _send_all(smtp_cfg, [u.email for u in recipients], subject, html, text, f"Document notification (doc={doc_id})")
    except Exception as exc:
        logger.warning("send_document_processed_notification failed (doc=%s): %s", doc_id, exc)


# ---------------------------------------------------------------------------
# Caregiver added
# ---------------------------------------------------------------------------

async def send_caregiver_added_notification(patient_id: str, caregiver_user_id: str) -> None:
    """Notify the newly added caregiver that they now have access to a patient."""
    try:
        from sqlalchemy import select
        from app.core.config import settings
        from app.core.database import AsyncSessionLocal
        from app.models.patient import Patient
        from app.models.user import User

        async with AsyncSessionLocal() as db:
            notify = await notify_settings(db)
            if not notify["caregiver_added"]:
                return
            smtp_cfg = await _get_smtp_config(db)
            if not smtp_cfg:
                return
            lang, _ = await _org(db)
            patient = (await db.execute(select(Patient).where(Patient.id == uuid.UUID(patient_id)))).scalar_one_or_none()
            caregiver = (await db.execute(select(User).where(User.id == uuid.UUID(caregiver_user_id)))).scalar_one_or_none()
            if not patient or not caregiver or not caregiver.is_active:
                return

        t = _T[lang]
        url = f"{settings.app_url}/patients/{patient_id}" if settings.app_url else None
        if notify["include_content"]:
            patient_name = f"{patient.given_name} {patient.family_name}"
            line = t["care_line"].format(patient=patient_name)
            subject = t["care_subject"].format(patient=patient_name)
            text = "\n".join(filter(None, [line, "", url, "", t["footer"]]))
            html = _page(lang, f"""  <h2 style="font-size:17px;margin-bottom:2px">{t["care_title"]}</h2>
  <p>{escape(line)}</p>
  {_button(url, t["care_button"])}""")
        else:
            subject, html, text = _contentless(url, lang, "caregiver")

        await _send_all(smtp_cfg, [caregiver.email], subject, html, text, "Caregiver-added notification")
    except Exception as exc:
        logger.warning("send_caregiver_added_notification failed: %s", exc)


# ---------------------------------------------------------------------------
# Invitation
# ---------------------------------------------------------------------------

async def send_invitation_email(to_email: str, token: str, inviter_id: str | None = None) -> None:
    """The sign-up link, with who invites and to what (ADR 054): neither is health data."""
    try:
        from app.core.config import settings
        from app.core.database import AsyncSessionLocal
        from app.models.user import User

        async with AsyncSessionLocal() as db:
            if not (await notify_settings(db))["invitation"]:
                return
            smtp_cfg = await _get_smtp_config(db)
            if not smtp_cfg:
                return
            lang, org_name = await _org(db)
            inviter = await db.get(User, uuid.UUID(inviter_id)) if inviter_id else None

        t = _T[lang]
        who = " ".join(filter(None, [inviter and inviter.first_name, inviter and inviter.last_name])) or t["someone"]
        url = f"{settings.app_url}/register?token={token}" if settings.app_url else None
        subject = t["inv_subject"].format(inviter=who)
        line = t["inv_line"].format(inviter=who, org=org_name)
        text = "\n".join([
            line, "",
            t["inv_here"].format(url=url) if url else t["inv_nolink"], "",
            t["inv_expires"], "",
            t["footer"],
        ])
        html = _page(lang, f"""  <h2 style="font-size:17px;margin-bottom:2px">{escape(subject)}</h2>
  <p>{escape(line)} {t["inv_expires"]}</p>
  {_button(url, t["inv_button"]) or f"<p>{t['inv_nolink']}</p>"}""")

        await _send_all(smtp_cfg, [to_email], subject, html, text, "Invitation")
    except Exception as exc:
        logger.warning("send_invitation_email failed: %s", exc)


# ---------------------------------------------------------------------------
# Event reminder
# ---------------------------------------------------------------------------

def _days_until(start_at: str | None) -> int | None:
    """Whole days from today to an all-day event's date, or None if unparseable."""
    from datetime import date
    if not start_at or len(start_at) < 10:
        return None
    try:
        return max((date.fromisoformat(start_at[:10]) - date.today()).days, 0)
    except ValueError:
        return None


async def send_event_reminder(event_id: str) -> None:
    """Send a 24-hour reminder to all caregivers for a calendar event."""
    try:
        from sqlalchemy import select
        from app.core.config import settings
        from app.core.database import AsyncSessionLocal
        from app.models.calendar import CalendarEvent

        async with AsyncSessionLocal() as db:
            notify = await notify_settings(db)
            if not notify["event_reminder"]:
                return
            smtp_cfg = await _get_smtp_config(db)
            if not smtp_cfg:
                return
            lang, _ = await _org(db)
            event = (await db.execute(select(CalendarEvent).where(CalendarEvent.id == uuid.UUID(event_id)))).scalar_one_or_none()
            if not event:
                return
            recipients, patient = await _get_caregivers_for_patient(db, event.patient_id)

        if not recipients or not patient:
            return

        t = _T[lang]
        url = f"{settings.app_url}/patients/{event.patient_id}/calendar" if settings.app_url else None
        # A deadline is a last date, not a date in the diary: say so, and say it in
        # days, because "tomorrow" is wrong for a reminder sent two weeks ahead (ADR 041).
        is_deadline = event.category == "deadline"
        when = _when(lang, _days_until(event.start_at) if is_deadline else 1)

        if notify["include_content"]:
            patient_name = f"{patient.given_name} {patient.family_name}"
            subject = (t["dl_subject"] if is_deadline else t["ev_subject"]).format(when=when, title=event.title)
            line = (t["dl_line"] if is_deadline else t["ev_line"]).format(title=event.title, patient=patient_name, when=when)
            advice = t["advice"] if is_deadline else None
            rows = [(label, v) for label, v in zip(t["ev_labels"], (event.start_at, event.location, event.provider)) if v]
            text = "\n".join(filter(lambda s: s is not None, [
                line, "",
                *(f"{label}: {v}" for label, v in rows),
                *(["", event.description] if event.description else []),
                *(["", advice] if advice else []),
                *(["", url] if url else []),
                "", t["footer"],
            ]))
            detail_rows = "".join(
                f"<tr><td style='padding:4px 0;color:#6b7280;width:90px'>{label}</td><td style='padding:4px 0'>{escape(v)}</td></tr>"
                for label, v in rows
            )
            html = _page(lang, f"""  <h2 style="font-size:17px;margin-bottom:2px">{t["dl_title"] if is_deadline else t["ev_title"]}: {escape(event.title)}</h2>
  <p style="color:#6b7280;margin-top:0">{t["for"]} <strong>{escape(patient_name)}</strong>, {when}</p>
  {"<table style='width:100%;border-collapse:collapse;margin:12px 0'>" + detail_rows + "</table>" if detail_rows else ""}
  {"<p style='font-size:14px;white-space:pre-line'>" + escape(event.description) + "</p>" if is_deadline and event.description else ""}
  {"<p style='font-size:13px;color:#6b7280'>" + escape(advice) + "</p>" if advice else ""}
  {_button(url, t["cal_button"])}""")
        else:
            subject, html, text = _contentless(url, lang, "deadline" if is_deadline else "event", when)

        await _send_all(smtp_cfg, [u.email for u in recipients], subject, html, text, f"Event reminder (event={event_id})")
    except Exception as exc:
        logger.warning("send_event_reminder failed (event=%s): %s", event_id, exc)
