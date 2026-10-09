"""Celery signal handlers that record every task execution in ``task_runs`` (issue #4).

Imported by ``celery_app`` so the handlers register in every worker process.
DB access reuses the worker's event loop (the asyncpg pool is loop-bound), matching
the pattern in ``app.workers.scheduler``.
"""

import asyncio
from datetime import UTC, datetime

from celery.signals import task_failure, task_postrun, task_prerun


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _summarize(args, kwargs) -> str | None:
    parts = []
    if args:
        parts.append(f"args={args!r}")
    if kwargs:
        parts.append(f"kwargs={kwargs!r}")
    s = " ".join(parts)
    if not s:
        return None
    return s[:497] + "..." if len(s) > 500 else s


async def _record_start(task_id: str, task_name: str, args_summary: str | None) -> None:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.task_run import TaskRun

    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(TaskRun).where(TaskRun.task_id == task_id))).scalar_one_or_none()
        now = datetime.now(UTC)
        if row:  # retry reuses the task_id
            row.task_name = task_name
            row.args_summary = args_summary
            row.status = "running"
            row.started_at = now
            row.finished_at = None
            row.error = None
        else:
            db.add(TaskRun(
                task_id=task_id, task_name=task_name, args_summary=args_summary,
                status="running", started_at=now,
            ))
        await db.commit()


async def _record_finish(task_id: str, status: str, error: str | None = None) -> None:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.task_run import TaskRun

    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(TaskRun).where(TaskRun.task_id == task_id))).scalar_one_or_none()
        if not row:
            return
        row.finished_at = datetime.now(UTC)
        row.status = status
        if error:
            row.error = error[:4000]
        await db.commit()


@task_prerun.connect
def _on_prerun(task_id=None, task=None, args=None, kwargs=None, **extra):
    try:
        _run(_record_start(task_id, getattr(task, "name", "unknown"), _summarize(args, kwargs)))
    except Exception:
        pass


@task_postrun.connect
def _on_postrun(task_id=None, task=None, state=None, **extra):
    try:
        _run(_record_finish(task_id, "success" if state == "SUCCESS" else "failure"))
    except Exception:
        pass


@task_failure.connect
def _on_failure(task_id=None, exception=None, einfo=None, **extra):
    try:
        error = str(einfo) if einfo else (str(exception) if exception else "unknown error")
        _run(_record_finish(task_id, "failure", error))
    except Exception:
        pass
