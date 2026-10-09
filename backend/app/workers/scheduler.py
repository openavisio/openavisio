"""Embedding scheduler, diary embedding, and event reminder tasks."""

import asyncio
import uuid

from app.workers.celery_app import celery_app


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task
def embedding_scheduler():
    """Find docs that need (re-)embedding and enqueue them."""
    from app.core.config import settings

    async def _scan():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.document import DocumentReference

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DocumentReference).where(
                    DocumentReference.is_deleted == False,  # noqa: E712
                    DocumentReference.processing_status == "extracted",
                    DocumentReference.extracted_text != None,  # noqa: E711
                ).limit(settings.embedding_scheduler_batch_size)
            )
            docs = result.scalars().all()
            from app.workers.pipeline import embedding_stage
            for doc in docs:
                embedding_stage.delay(str(doc.id))
            return len(docs)

    count = _run(_scan())
    return {"enqueued": count}


@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=2, default_retry_delay=30)
def diary_embedding_job(self, entry_id: str):
    """Embed a diary entry for RAG."""
    from app.core.config import settings
    import httpx

    async def _embed():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.diary import DiaryEntry
        from app.models.chat import DocumentChunk

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(DiaryEntry).where(DiaryEntry.id == uuid.UUID(entry_id)))
            entry = result.scalar_one_or_none()
            if not entry:
                return

            if not (entry.general_notes or entry.nutrition_notes):
                return

            # diary notes are ciphertext at rest (ADR-031): decrypt to embed,
            # re-encrypt the chunk copy under the same patient KEK
            from app.core.encryption import decrypt_str, encrypt_str
            from app.core.patient_keys import get_patient_kek
            kek = await get_patient_kek(db, entry.patient_id)
            text_parts = [decrypt_str(v, kek) for v in (entry.general_notes, entry.nutrition_notes) if v]
            text = " ".join(text_parts)
            async with httpx.AsyncClient(timeout=30, headers=settings.ai_service_headers) as client:
                resp = await client.post(f"{settings.ai_service_url}/embed", json={"texts": [text]})
                if resp.status_code != 200:
                    return
                embedding = resp.json()["embeddings"][0]

            # Remove old chunks
            existing = await db.execute(select(DocumentChunk).where(DocumentChunk.diary_entry_id == uuid.UUID(entry_id)))
            for chunk in existing.scalars().all():
                await db.delete(chunk)

            db.add(DocumentChunk(
                diary_entry_id=uuid.UUID(entry_id),
                patient_id=entry.patient_id,
                chunk_index=0,
                content=encrypt_str(text, kek),
                embedding=embedding,
            ))
            await db.commit()

    _run(_embed())


@celery_app.task
def event_reminder_scheduler():
    """Send reminder emails for upcoming calendar events.

    An appointment is reminded once, the day before. A Widerspruch deadline is
    reminded twice, at 14 and 3 days (ADR 041): 24 hours is useless for something
    that has to be understood, written and posted, and missing it is final.
    """

    async def _scan():
        from datetime import UTC, datetime, timedelta
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.calendar import CalendarEvent
        from app.services.email import send_event_reminder

        # Lead time in hours per stage. Index = reminder_stage already done.
        # A Widerspruch is written in an evening, so 14 and 3 days. An expiring
        # Einstufung needs a follow-up application and a fresh assessment, which take
        # months, so 90 and 30 (ADR 042) — hence the lead depends on where the
        # deadline came from, not on its category alone.
        LEAD_HOURS = {"deadline": [14 * 24, 3 * 24]}
        EXPIRY_LEAD = [90 * 24, 30 * 24]
        DEFAULT_LEAD = [24]
        now = datetime.now(UTC)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CalendarEvent).where(
                    CalendarEvent.is_deleted.is_(False),
                    CalendarEvent.status == "scheduled",
                )
            )
            events = result.scalars().all()

            to_remind = []
            for e in events:
                stages = (EXPIRY_LEAD if e.purpose == "einstufung_expiry"
                          else LEAD_HOURS.get(e.category, DEFAULT_LEAD))
                if not e.start_at or e.reminder_stage >= len(stages):
                    continue
                # A Bescheid uploaded with 2 days left would otherwise hit both stages
                # an hour apart. One mail a day is enough to be taken seriously.
                if e.reminder_sent_at and (now - e.reminder_sent_at) < timedelta(hours=20):
                    continue
                lead = stages[e.reminder_stage]
                # An hourly scan with a two-hour window: a deadline created inside its
                # own lead time (a Bescheid uploaded late) would otherwise never match,
                # so anything already past its lead point is due now.
                if _parse_event_dt(e.start_at, now, now + timedelta(hours=lead + 1)):
                    to_remind.append(e)

            for event in to_remind:
                await send_event_reminder(str(event.id))
                event.reminder_sent_at = now
                event.reminder_stage += 1

            if to_remind:
                await db.commit()

        return {"reminded": len(to_remind)}

    return _run(_scan())


@celery_app.task
def retention_purge_scheduler():
    """Enforce per-category retention: soft-delete records past their window (#16)."""

    async def _purge():
        from app.core.database import AsyncSessionLocal
        from app.services.governance import ensure_categories_seeded, run_retention_purge

        async with AsyncSessionLocal() as db:
            await ensure_categories_seeded(db)
            return await run_retention_purge(db)

    return _run(_purge())


def _parse_event_dt(start_at: str, window_start, window_end) -> bool:
    """Return True if start_at falls within the reminder window."""
    from datetime import UTC, datetime, timezone
    try:
        dt = datetime.fromisoformat(start_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return window_start <= dt <= window_end
    except ValueError:
        return False
