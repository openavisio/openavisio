"""Tell someone when processing breaks (#115).

Today a deploy left the Celery worker on stale code and every single document
upload failed for hours. Nobody found out until a user reported it: a failed
document sets `processing_status="failed"` and then sits there, silently.

Hourly check, e-mail to the admins, on the SMTP the app already uses for
notifications. No new dependency, no new service. Alerting properly (error
tracking, metrics) is a bigger job — this is the floor that would have caught
today's outage.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_WINDOW_HOURS = 1
# One failure is a bad scan; several in an hour is a broken pipeline.
_THRESHOLD = 3


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task
def failed_document_watchdog():
    """E-mail the admins when documents start piling up in `failed`."""

    async def _check():
        from sqlalchemy import func, select

        from app.core.database import AsyncSessionLocal
        from app.models.document import DocumentReference
        from app.models.user import User
        from app.services.email import _get_smtp_config, _send_smtp

        since = datetime.now(UTC) - timedelta(hours=_WINDOW_HOURS)

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(DocumentReference.processing_error, func.count())
                .where(
                    DocumentReference.processing_status == "failed",
                    DocumentReference.updated_at >= since,
                    DocumentReference.is_deleted == False,  # noqa: E712
                )
                .group_by(DocumentReference.processing_error)
            )).all()

            total = sum(count for _, count in rows)
            if total < _THRESHOLD:
                return

            admins = (await db.execute(
                select(User).where(
                    User.role == "admin",
                    User.is_active == True,  # noqa: E712
                    User.is_deleted == False,  # noqa: E712
                )
            )).scalars().all()

            # On a hosted Deployment the admins are the customer, who cannot fix a
            # worker stuck on stale code, and the operator has no account here by
            # design. Empty on a self-hosted install, so nothing changes there (#250).
            from app.core.config import settings

            recipients = [a.email for a in admins]
            if settings.ops_alert_email and settings.ops_alert_email not in recipients:
                recipients.append(settings.ops_alert_email)
            if not recipients:
                logger.warning("%d documents failed in the last hour, but nobody to tell", total)
                return

            smtp = await _get_smtp_config(db)
            if not smtp:
                # The log is the last resort — better than silence.
                logger.error("%d documents failed in the last hour; no SMTP configured to report it", total)
                return

            breakdown = "\n".join(f"  {count}x  {err or 'unbekannt'}" for err, count in rows)
            subject = f"OpenAvisio: {total} Dokumente in der letzten Stunde fehlgeschlagen"
            text = (
                f"{total} Dokumente konnten in der letzten Stunde nicht verarbeitet werden.\n\n"
                f"Fehler:\n{breakdown}\n\n"
                "Häufigste Ursachen: der AI-Service ist nicht erreichbar, oder ein Deploy hat "
                "den Celery-Worker auf altem Code stehen lassen.\n"
            )
            html = f"<p><b>{total} Dokumente</b> konnten in der letzten Stunde nicht verarbeitet werden.</p><pre>{breakdown}</pre>"

            for address in recipients:
                try:
                    await asyncio.to_thread(_send_smtp, smtp, address, subject, html, text)
                except Exception as e:  # noqa: BLE001 — one bad address must not stop the rest
                    logger.error("watchdog: could not e-mail %s: %s", address, e)

            logger.warning("watchdog: %d failed documents in the last hour, %d notified", total, len(recipients))

    _run(_check())
