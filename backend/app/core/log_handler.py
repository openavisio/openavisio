import asyncio
import json
import logging
import queue
import threading
from collections import deque
from datetime import UTC, datetime

_ring_buffer: deque = deque(maxlen=500)
_db_queue: asyncio.Queue = asyncio.Queue()
REDIS_CHANNEL = "openavisio:logs"
_handler_installed = False
_source = "api"
LOG_RETENTION_DAYS = 30


class _RedisLogHandler(logging.Handler):
    """Thread-safe log handler that publishes to Redis via a background thread.

    Publishing from emit() directly fails with redis-py 6.x because the sync
    client uses asyncio internally — calling it inside uvicorn's running event
    loop raises RuntimeError. A queue + dedicated publisher thread avoids this.
    """

    def __init__(self, redis_url: str) -> None:
        super().__init__()
        self._url = redis_url
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._thread = threading.Thread(target=self._publisher, daemon=True)
        self._thread.start()

    def _publisher(self) -> None:
        import redis as _redis
        client = _redis.Redis.from_url(self._url, decode_responses=True, socket_connect_timeout=2)
        while True:
            try:
                payload = self._queue.get()
                if payload is None:
                    break
                client.publish(REDIS_CHANNEL, payload)
            except Exception:
                pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry: dict = {
                "ts": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
                "source": _source,
            }
            if record.exc_info:
                import traceback as _tb
                entry["exc"] = "".join(_tb.format_exception(*record.exc_info))
            self._queue.put_nowait(json.dumps(entry, default=str))
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        self._queue.put_nowait(None)
        super().close()


def setup_log_handler(redis_url: str, source: str = "api") -> None:
    global _handler_installed, _source
    if _handler_installed:
        return
    _handler_installed = True
    _source = source

    handler = _RedisLogHandler(redis_url)

    # Root logger — catches anything that still propagates
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)

    # Uvicorn loggers set propagate=False, so attach our handler directly
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.addHandler(handler)
        if lg.level == logging.NOTSET or lg.level > logging.INFO:
            lg.setLevel(logging.INFO)

    # App and Celery loggers at DEBUG; don't propagate to avoid double-publish
    for name in ("app", "celery"):
        lg = logging.getLogger(name)
        lg.addHandler(handler)
        lg.setLevel(logging.DEBUG)
        lg.propagate = False

    # Suppress noisy third-party libs
    for name in ("sqlalchemy", "httpx", "httpcore", "urllib3", "asyncio", "kombu", "amqp"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_log_history() -> list[dict]:
    return list(_ring_buffer)


async def start_ring_buffer_subscriber(redis_url: str) -> None:
    """Background task: subscribes to Redis log channel and populates the in-process ring buffer."""
    import redis.asyncio as aioredis

    client = aioredis.Redis.from_url(redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(REDIS_CHANNEL)
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                try:
                    entry = json.loads(message["data"])
                    _ring_buffer.append(entry)
                    await _db_queue.put(entry)
                except Exception:
                    pass
            await asyncio.sleep(0)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(REDIS_CHANNEL)
        await client.aclose()


async def start_db_flush_task(engine) -> None:
    """Background task: batch-flushes log entries from the queue to the database every 5 seconds."""
    from datetime import timedelta

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.log_entry import LogEntry

    flush_counter = 0
    try:
        while True:
            await asyncio.sleep(5)
            batch: list[dict] = []
            try:
                while True:
                    batch.append(_db_queue.get_nowait())
            except asyncio.QueueEmpty:
                pass

            if not batch:
                flush_counter += 1
                if flush_counter >= 720:  # prune once every hour (720 × 5s)
                    flush_counter = 0
                    cutoff = datetime.now(UTC) - timedelta(days=LOG_RETENTION_DAYS)
                    try:
                        async with AsyncSession(engine) as session:
                            await session.execute(delete(LogEntry).where(LogEntry.timestamp < cutoff))
                            await session.commit()
                    except Exception:
                        pass
                continue

            flush_counter = 0
            try:
                async with AsyncSession(engine) as session:
                    for entry in batch:
                        try:
                            ts = datetime.fromisoformat(entry["ts"])
                        except Exception:
                            ts = datetime.now(UTC)
                        session.add(LogEntry(
                            level=entry.get("level", "INFO")[:10],
                            logger=entry.get("logger", "unknown")[:200],
                            message=entry.get("msg", ""),
                            source=entry.get("source", "unknown")[:50],
                            timestamp=ts,
                            exc=entry.get("exc"),
                        ))
                    await session.commit()
            except Exception:
                pass
    except asyncio.CancelledError:
        pass
