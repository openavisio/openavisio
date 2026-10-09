"""Tests for Celery task-run tracking admin endpoint (issue #4)."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.task_run import TaskRun
from app.models.user import User


async def _user(db: AsyncSession, email: str, role: str = "admin") -> User:
    u = User(email=email, hashed_password=hash_password("Pass1!"), role=role, is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _seed(db: AsyncSession) -> None:
    base = datetime(2026, 7, 2, 10, 0, 0, tzinfo=UTC)
    rows = [
        TaskRun(task_id="t1", task_name="app.workers.pipeline.ocr_stage", status="success",
                started_at=base, finished_at=base + timedelta(seconds=5), created_at=base),
        TaskRun(task_id="t2", task_name="app.workers.scheduler.embedding_scheduler", status="running",
                started_at=base + timedelta(minutes=1), created_at=base + timedelta(minutes=1)),
        TaskRun(task_id="t3", task_name="app.workers.scheduler.event_reminder_scheduler", status="failure",
                started_at=base + timedelta(minutes=2), finished_at=base + timedelta(minutes=2),
                error="boom traceback", created_at=base + timedelta(minutes=2)),
    ]
    for r in rows:
        db.add(r)
    await db.commit()


async def test_lists_all_job_types_newest_first(client: AsyncClient, db: AsyncSession):
    await _user(db, "adm1@test.com")
    await _seed(db)
    h = await _auth(client, "adm1@test.com")

    rows = (await client.get("/api/admin/logs/task-runs", headers=h)).json()
    assert [r["task_id"] for r in rows] == ["t3", "t2", "t1"]  # created_at desc
    names = {r["task_name"] for r in rows}
    assert "app.workers.scheduler.embedding_scheduler" in names
    assert "app.workers.scheduler.event_reminder_scheduler" in names  # not just pipeline
    failed = next(r for r in rows if r["task_id"] == "t3")
    assert failed["status"] == "failure"
    assert failed["error"] == "boom traceback"


async def test_filter_by_status_and_name(client: AsyncClient, db: AsyncSession):
    await _user(db, "adm2@test.com")
    await _seed(db)
    h = await _auth(client, "adm2@test.com")

    only_failure = (await client.get("/api/admin/logs/task-runs?status=failure", headers=h)).json()
    assert [r["task_id"] for r in only_failure] == ["t3"]

    by_name = (await client.get(
        "/api/admin/logs/task-runs?name=app.workers.scheduler.embedding_scheduler", headers=h)).json()
    assert [r["task_id"] for r in by_name] == ["t2"]


async def test_requires_admin(client: AsyncClient, db: AsyncSession):
    await _user(db, "plain@test.com", role="user")
    h = await _auth(client, "plain@test.com")
    assert (await client.get("/api/admin/logs/task-runs", headers=h)).status_code == 403


def test_gpu_stages_are_routed_to_the_serial_queue():
    """One model, one card (#152): un-routing a GPU stage re-enables the 4-wide
    stampede that produced five timeouts out of nine documents."""
    from app.workers.celery_app import celery_app

    routes = celery_app.conf.task_routes
    for stage in ("ocr_stage", "extraction_stage", "embedding_stage"):
        assert routes[f"app.workers.pipeline.{stage}"]["queue"] == "gpu"
