import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access, resolve_patient_access
from app.core.config import settings
from app.core.database import get_db
from app.deps import get_current_user
from app.models.audit import AuditLog
from app.models.calendar import CalendarEvent, CalendarFeed, EventCategory
from app.models.diary import DiaryEntry
from app.models.document import DocumentReference
from app.models.incident import Incident
from app.models.medication import MedicationStatement
from app.models.patient import Patient
from app.models.user import User
from app.schemas.calendar import (
    CalendarEventCreateRequest,
    CalendarEventDto,
    CalendarEventUpdateRequest,
    CalendarFeedCreatedDto,
    CalendarFeedDto,
    CalendarFeedItem,
    IncidentFrequencyPoint,
    PatternDetectionDto,
    TrendDataDto,
    TrendPoint,
)
from app.services.calendar_feed import build_ics, generate_token, hash_token, window_start

router = APIRouter()

# Muted, warm-harmonized category colors to sit with the claude.ai palette (#74),
# kept distinguishable from each other and from the clay primary.
_TYPE_COLORS = {
    "appointment": "#4f7cac",
    "milestone": "#c79a45",
    "deadline": "#b06a3b",  # a last date, not an appointment (ADR 041)
    "incident": "#c0503f",
    "diary": "#5f8a6b",
    "condition": "#8a6d9c",
    "medication": "#3f8c7d",
    "document": "#7b8794",
}


@router.get("/patients/{patient_id}/calendar/events", response_model=list[CalendarEventDto])
async def list_events(
    patient_id: uuid.UUID,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = select(CalendarEvent).where(CalendarEvent.patient_id == patient_id, CalendarEvent.is_deleted == False)  # noqa: E712
    if from_:
        q = q.where(CalendarEvent.start_at >= from_)
    if to:
        q = q.where(CalendarEvent.start_at <= to)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/patients/{patient_id}/calendar/events", response_model=CalendarEventDto, status_code=status.HTTP_201_CREATED)
async def create_event(
    patient_id: uuid.UUID,
    body: CalendarEventCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    event = CalendarEvent(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.get("/calendar/events/{event_id}", response_model=CalendarEventDto)
async def get_event(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.is_deleted == False))  # noqa: E712
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(event.patient_id, user, db)
    return event


@router.put("/calendar/events/{event_id}", response_model=CalendarEventDto)
async def update_event(
    event_id: uuid.UUID,
    body: CalendarEventUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.is_deleted == False))  # noqa: E712
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(event.patient_id, user, db, AccessLevel.contribute)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(event, field, value)
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/calendar/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.is_deleted == False))  # noqa: E712
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(event.patient_id, user, db, AccessLevel.contribute)
    event.is_deleted = True
    await db.commit()


@router.get("/patients/{patient_id}/calendar/feed", response_model=list[CalendarFeedItem])
async def get_feed(
    patient_id: uuid.UUID,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    types: str | None = Query(None),
    q: str | None = Query(None),
    mood: int | None = Query(None),
    incident_type: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    items: list[CalendarFeedItem] = []

    # Calendar events
    ev_q = select(CalendarEvent).where(CalendarEvent.patient_id == patient_id, CalendarEvent.is_deleted == False)  # noqa: E712
    if from_:
        ev_q = ev_q.where(CalendarEvent.start_at >= from_)
    if to:
        ev_q = ev_q.where(CalendarEvent.start_at <= to)
    events = (await db.execute(ev_q)).scalars().all()
    for ev in events:
        ev_type = ev.category if ev.category in ("milestone", "deadline") else "appointment"
        if not types or ev_type in types:
            if not q or q.lower() in ev.title.lower():
                items.append(CalendarFeedItem(
                    id=ev.id, title=ev.title, start=ev.start_at, end=ev.end_at,
                    all_day=ev.all_day, type=ev_type, color=_TYPE_COLORS[ev_type],
                    developmental_domain=ev.developmental_domain,
                ))

    # Incidents
    inc_q = select(Incident).where(Incident.patient_id == patient_id, Incident.is_deleted == False)  # noqa: E712
    if from_:
        inc_q = inc_q.where(Incident.occurred_at >= from_)
    if to:
        inc_q = inc_q.where(Incident.occurred_at <= to)
    if incident_type:
        inc_q = inc_q.where(Incident.incident_type == incident_type)
    incidents = (await db.execute(inc_q)).scalars().all()
    for inc in incidents:
        if not types or "incident" in types:
            title = inc.incident_type_display or inc.incident_type
            if not q or q.lower() in title.lower():
                items.append(CalendarFeedItem(
                    id=inc.id, title=title, start=inc.occurred_at, end=None,
                    all_day=False, type="incident", color=_TYPE_COLORS["incident"],
                ))

    # Diary entries
    di_q = select(DiaryEntry).where(DiaryEntry.patient_id == patient_id, DiaryEntry.is_deleted == False)  # noqa: E712
    if from_:
        di_q = di_q.where(DiaryEntry.entry_date >= from_)
    if to:
        di_q = di_q.where(DiaryEntry.entry_date <= to)
    if mood is not None:
        di_q = di_q.where(DiaryEntry.mood == mood)
    diary = (await db.execute(di_q)).scalars().all()
    for entry in diary:
        if not types or "diary" in types:
            title = entry.subject or f"Diary — {entry.entry_date}"
            if not q or q.lower() in title.lower():
                items.append(CalendarFeedItem(
                    id=entry.id, title=title, start=entry.entry_date, end=None,
                    all_day=True, type="diary", color=_TYPE_COLORS["diary"],
                ))

    # Medications — ONE item spanning the course, not two loose pills (#130).
    #
    # Two problems with the old start/end pills: a caregiver could not see what was
    # being taken ON a given day, and the range filter tested each endpoint on its
    # own — so a medication that began before the visible month and ends after it
    # produced no items at all, and simply vanished from the month it was actually
    # taken in.
    if not types or "medication" in types:
        med_url = f"/patients/{patient_id}/medications"
        meds = (await db.execute(
            select(MedicationStatement).where(
                MedicationStatement.patient_id == patient_id, MedicationStatement.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
        for m in meds:
            if q and q.lower() not in m.medication_display.lower():
                continue
            # No start date, no bar. Drawing an undated medication from the beginning
            # of time would be an invention; it stays on the medications page, where
            # it can be given a date (#128).
            if not m.effective_start:
                continue
            # overlap, not containment: does the course touch the window at all?
            if to and m.effective_start > to:
                continue
            # An open-ended course means "still running TODAY" — not "will still be
            # taken in 2030". Without this the bar marched through every future
            # month forever, which is a claim about the future we cannot make.
            effective_end = m.effective_end or date.today().isoformat()
            if from_ and effective_end < from_:
                continue
            # the dose is the point — "Valproat" alone sends you off to another page
            title = f"{m.medication_display} · {m.dosage_text}" if m.dosage_text else m.medication_display
            items.append(CalendarFeedItem(
                id=m.id, title=title, start=m.effective_start,
                end=m.effective_end, all_day=True, type="medication",
                color=_TYPE_COLORS["medication"], url=med_url,
            ))

    # Documents — a marker on the document's own date (issued date, else upload date)
    if not types or "document" in types:
        doc_rows = (await db.execute(
            select(DocumentReference).where(
                DocumentReference.patient_id == patient_id, DocumentReference.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
        for d in doc_rows:
            when = d.issued_date.isoformat() if d.issued_date else d.created_at.date().isoformat()
            if (from_ and when < from_) or (to and when > to):
                continue
            # The file name is usually a scanner artefact (img20240405_08273634.pdf).
            # Send the issuer and the class; the client turns the class into a
            # localised label (#130 follow-up, same fix as the documents list).
            # detected_provider only: correspondent is not eager-loaded here, and a
            # lazy load would blow up in the async session
            issuer = d.detected_provider
            title = d.type or d.description or issuer or d.file_name or "Dokument"
            if q and q.lower() not in title.lower():
                continue
            items.append(CalendarFeedItem(
                id=d.id, title=issuer or title, start=when, end=None, all_day=True,
                type="document", color=_TYPE_COLORS["document"],
                classification=d.document_classification,
                url=f"/patients/{patient_id}/documents/{d.id}",
            ))

    items.sort(key=lambda x: x.start, reverse=True)
    return items


@router.get("/patients/{patient_id}/calendar/trends", response_model=TrendDataDto)
async def get_trends(
    patient_id: uuid.UUID,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    granularity: str = Query("day"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = select(DiaryEntry).where(DiaryEntry.patient_id == patient_id, DiaryEntry.is_deleted == False)  # noqa: E712
    if from_:
        q = q.where(DiaryEntry.entry_date >= from_)
    if to:
        q = q.where(DiaryEntry.entry_date <= to)
    entries = (await db.execute(q)).scalars().all()

    mood_trend = [TrendPoint(date=e.entry_date, value=float(e.mood) if e.mood else None) for e in entries if e.mood is not None]
    pain_trend = [TrendPoint(date=e.entry_date, value=float(e.pain_level) if e.pain_level else None) for e in entries if e.pain_level is not None]
    sleep_trend = [TrendPoint(date=e.entry_date, value=e.sleep_hours) for e in entries if e.sleep_hours is not None]

    inc_q = select(Incident).where(Incident.patient_id == patient_id, Incident.is_deleted == False)  # noqa: E712
    if from_:
        inc_q = inc_q.where(Incident.occurred_at >= from_)
    incidents = (await db.execute(inc_q)).scalars().all()
    freq: dict[str, int] = defaultdict(int)
    for inc in incidents:
        day = inc.occurred_at[:10]
        freq[day] += 1
    incident_frequency = [IncidentFrequencyPoint(date=d, count=c) for d, c in sorted(freq.items())]

    return TrendDataDto(mood_trend=mood_trend, pain_trend=pain_trend, sleep_trend=sleep_trend, incident_frequency=incident_frequency)


@router.get("/patients/{patient_id}/calendar/patterns", response_model=PatternDetectionDto)
async def get_patterns(
    patient_id: uuid.UUID,
    window_days: int = Query(90, alias="windowDays"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    cutoff = (datetime.now(UTC) - timedelta(days=window_days)).isoformat()
    result = await db.execute(select(Incident).where(
        Incident.patient_id == patient_id,
        Incident.is_deleted == False,  # noqa: E712
        Incident.occurred_at >= cutoff,
    ).order_by(Incident.occurred_at.desc()))
    incidents = result.scalars().all()

    # Last incident badges by type
    by_type: dict[str, str] = {}
    for inc in incidents:
        if inc.incident_type not in by_type:
            by_type[inc.incident_type] = inc.occurred_at

    badges = [{"type": t, "last_occurred": d} for t, d in by_type.items()]
    return PatternDetectionDto(last_incident_badges=badges)


# --- iCal feed (ADR-037) -----------------------------------------------------

_FEED_HEADERS = {
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
    "Cache-Control": "no-store",
}


def _feed_audit(db: AsyncSession, user: User, action: str, feed_id, changes: dict | None = None) -> None:
    name = " ".join(filter(None, [user.first_name, user.last_name])) or user.email
    db.add(AuditLog(timestamp=datetime.now(UTC), user_id=user.id, user_name=name,
                    entity_type="CalendarFeed", entity_id=str(feed_id), action=action, changes=changes))


@router.post("/patients/{patient_id}/calendar/feeds", response_model=CalendarFeedCreatedDto, status_code=201)
async def create_calendar_feed(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mint a subscription URL. The plaintext token is returned once and never again."""
    await require_patient_access(patient_id, user, db)
    token, token_hash = generate_token()
    feed = CalendarFeed(patient_id=patient_id, user_id=user.id, token_hash=token_hash)
    db.add(feed)
    await db.flush()
    _feed_audit(db, user, "created", feed.id)
    await db.commit()
    await db.refresh(feed)
    base = settings.app_url.rstrip("/") if settings.app_url else ""
    return CalendarFeedCreatedDto(**CalendarFeedDto.model_validate(feed).model_dump(),
                                  url=f"{base}/api/public/calendar/{token}.ics")


@router.get("/patients/{patient_id}/calendar/feeds", response_model=list[CalendarFeedDto])
async def list_calendar_feeds(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Only the caller's own feeds — another Caregiver's subscription is not their business."""
    await require_patient_access(patient_id, user, db)
    rows = await db.execute(select(CalendarFeed).where(
        CalendarFeed.patient_id == patient_id,
        CalendarFeed.user_id == user.id,
        CalendarFeed.revoked_at == None,  # noqa: E711
        CalendarFeed.is_deleted == False,  # noqa: E712
    ).order_by(CalendarFeed.created_at.desc()))
    return list(rows.scalars().all())


@router.post("/patients/{patient_id}/calendar/feeds/{feed_id}/revoke", response_model=CalendarFeedDto)
async def revoke_calendar_feed(
    patient_id: uuid.UUID,
    feed_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    feed = (await db.execute(select(CalendarFeed).where(
        CalendarFeed.id == feed_id,
        CalendarFeed.patient_id == patient_id,
        CalendarFeed.user_id == user.id,
        CalendarFeed.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not feed.revoked_at:
        feed.revoked_at = datetime.now(UTC)
        _feed_audit(db, user, "updated", feed.id, {"revoked": True})
        await db.commit()
        await db.refresh(feed)
    return feed


@router.get("/public/calendar/{token}.ics")
async def public_calendar_feed(token: str, db: AsyncSession = Depends(get_db)):
    """Anonymous, token-only. Every miss returns the same 404, so the endpoint
    never reveals which feeds exist."""
    feed = (await db.execute(select(CalendarFeed).where(
        CalendarFeed.token_hash == hash_token(token),
        CalendarFeed.revoked_at == None,  # noqa: E711
        CalendarFeed.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # The feed rides on the subscriber's own care-circle access: losing it here
    # switches the subscription off with no separate revocation step (ADR-037).
    subscriber = (await db.execute(select(User).where(
        User.id == feed.user_id, User.is_active == True, User.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not subscriber or not await resolve_patient_access(feed.patient_id, subscriber, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    patient = (await db.execute(select(Patient).where(
        Patient.id == feed.patient_id, Patient.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    rows = await db.execute(select(CalendarEvent).where(
        CalendarEvent.patient_id == feed.patient_id,
        CalendarEvent.category == EventCategory.appointment,
        CalendarEvent.start_at >= window_start(),
        CalendarEvent.is_deleted == False,  # noqa: E712
    ).order_by(CalendarEvent.start_at))

    label = " ".join(filter(None, [patient.given_name, patient.family_name])) or "OpenAvisio"
    body = build_ics(list(rows.scalars().all()), label)

    feed.last_accessed_at = datetime.now(UTC)
    await db.commit()
    return Response(content=body, media_type="text/calendar; charset=utf-8", headers=_FEED_HEADERS)
