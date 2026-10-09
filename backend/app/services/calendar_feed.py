"""iCal feed for a Patient's appointments — see docs/adr/037-calendar-feed-is-one-way-ical.md.

One-way: the feed is a view, nothing writes back. Token handling mirrors
services/share_link.py (ADR-021); the calendar text is built here.
"""

from datetime import UTC, date, datetime, timedelta

from app.models.calendar import CalendarEvent
from app.services.share_link import generate_token, hash_token  # noqa: F401 — same 256-bit token scheme (ADR-021)

# ponytail: fixed window, not a per-feed setting. Exporting a full treatment
# history into a third-party cloud serves nobody; future-only makes last week's
# appointment vanish at midnight and reads as broken. Make it configurable when
# someone actually asks for a different number.
LOOKBACK_DAYS = 90


def window_start(today: date | None = None) -> str:
    """Oldest start_at to include, as an ISO date string.

    Compared lexicographically against start_at (a String(50) holding ISO text),
    which is what routers/calendar.py already does.
    """
    return ((today or datetime.now(UTC).date()) - timedelta(days=LOOKBACK_DAYS)).isoformat()


def _escape(text: str) -> str:
    """RFC 5545 text escaping: backslash, semicolon, comma, newline."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _stamp(value: str) -> tuple[str, bool]:
    """Split a stored start_at into (iCal value, is_date_only).

    start_at is either a bare ISO date ("2026-03-14") or a naive local timestamp
    ("2026-03-14T09:30:00"); routers/documents.py produces both. Dates become
    all-day entries. Timestamps are emitted as FLOATING time — no Z, no TZID —
    so the subscriber's calendar reads them in its own timezone.

    ponytail: floating breaks for a Caregiver travelling outside their Patient's
    timezone. No timezone is recorded anywhere on the event, and the Deployment's
    TZ is wrong for a scattered Organization (ADR-037). Upgrade path is a timezone
    on the Patient; the feed is per-Patient already, so only this function changes.
    """
    v = (value or "").strip()
    if "T" not in v:
        return v.replace("-", ""), True
    day, _, clock = v.partition("T")
    clock = clock.split("+")[0].split("Z")[0].replace(":", "")
    clock = (clock + "000000")[:6]
    return f"{day.replace('-', '')}T{clock}", False


def _event_lines(ev: CalendarEvent, now_stamp: str) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{ev.id}@openavisio",
        f"DTSTAMP:{now_stamp}",
        f"SUMMARY:{_escape(ev.title or '')}",
    ]
    start, date_only = _stamp(ev.start_at)
    lines.append(f"DTSTART;VALUE=DATE:{start}" if date_only else f"DTSTART:{start}")
    if not date_only and ev.end_at and not (end := _stamp(ev.end_at))[1]:
        lines.append(f"DTEND:{end[0]}")
    if ev.location:
        lines.append(f"LOCATION:{_escape(ev.location)}")
    # provider and purpose are the two fields the pipeline fills; a caregiver
    # reading "Termin" in their phone learnt nothing.
    body = " — ".join(filter(None, [ev.provider, ev.purpose or ev.description]))
    if body:
        lines.append(f"DESCRIPTION:{_escape(body)}")
    lines.append("END:VEVENT")
    return lines


def build_ics(events: list[CalendarEvent], patient_label: str, now: datetime | None = None) -> str:
    """Render appointments as an RFC 5545 calendar. No VALARM: reminders are the
    subscriber's own setting, and OpenAvisio has its own reminder path.

    ponytail: lines are not folded at 75 octets as RFC 5545 asks. Google, Apple and
    Outlook all parse long lines; fold here if a stricter client ever shows up.
    """
    now_stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OpenAvisio//Calendar Feed//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(patient_label)}",
    ]
    for ev in events:
        lines.extend(_event_lines(ev, now_stamp))
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
