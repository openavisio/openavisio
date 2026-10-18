"""An unhandled error answers with an id and tells the operator (ADR 053).

The mail carries the id, the time, the route and the exception's class, never its message or the
request: either may hold health data. At most one mail per hour per Deployment; the log has all.
"""

import asyncio
import logging
import secrets
from datetime import UTC, datetime

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)
_tasks: set[asyncio.Task] = set()


async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    error_id = secrets.token_hex(4)
    route = getattr(request.scope.get("route"), "path", None) or request.url.path
    logger.error("error %s on %s %s", error_id, request.method, route, exc_info=exc)
    if settings.ops_alert_email:
        task = asyncio.create_task(_tell_operator(error_id, request.method, route, type(exc).__name__,
                                                  request.headers.get("host", "?")))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "error_id": error_id})


async def _tell_operator(error_id: str, method: str, route: str, kind: str, host: str) -> None:
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        try:
            if not await r.set("ops:error-mail", error_id, nx=True, ex=3600):
                return  # one mail an hour is a signal; the rest are in the log under their ids
        finally:
            await r.aclose()

        from app.core.database import AsyncSessionLocal
        from app.services.email import _get_smtp_config, _send_smtp
        async with AsyncSessionLocal() as db:
            smtp = await _get_smtp_config(db)
        if not smtp:
            return
        when = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        text = (f"Fehler {error_id} auf {host}\n\n{when}\n{method} {route}\n{kind}\n\n"
                "Weitere Fehler in dieser Stunde stehen nur im Log (docker compose logs backend).\n")
        await asyncio.to_thread(_send_smtp, smtp, settings.ops_alert_email, f"OpenAvisio: Fehler {error_id} auf {host}",
                                f"<pre>{text}</pre>", text)
    except Exception as e:  # noqa: BLE001 — reporting an error must never raise one
        logger.warning("could not report error %s: %s", error_id, e)
