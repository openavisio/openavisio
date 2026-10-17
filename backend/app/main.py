import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core.log_handler import setup_log_handler, start_db_flush_task, start_ring_buffer_subscriber
from app.models import Base  # noqa: F401 — ensure models registered
from app.routers import (
    access,
    admin,
    auth,
    calendar,
    chat,
    conditions,
    correspondents,
    dashboard,
    dev,
    diary,
    documents,
    einstufungen,
    emergency_plan,
    care_notes,
    carer_updates,
    handouts,
    intake_forms,
    expenses,
    export,
    groups,
    incidents,
    medications,
    observations,
    organization,
    passkey,
    patients,
    share_links,
    sharing,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_log_handler(settings.redis_url, source="api")
    subscriber_task = asyncio.create_task(start_ring_buffer_subscriber(settings.redis_url))
    flush_task = asyncio.create_task(start_db_flush_task(engine))
    yield
    subscriber_task.cancel()
    flush_task.cancel()
    await asyncio.gather(subscriber_task, flush_task, return_exceptions=True)


app = FastAPI(
    title="OpenAvisio API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
)

from app.demo import read_only  # noqa: E402 — a no-op unless this is the public demo
app.middleware("http")(read_only)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(passkey.router, prefix="/api/auth", tags=["passkey"])
app.include_router(patients.router, prefix="/api", tags=["patients"])
app.include_router(observations.router, prefix="/api", tags=["observations"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(incidents.router, prefix="/api", tags=["incidents"])
app.include_router(einstufungen.router, prefix="/api", tags=["einstufungen"])
app.include_router(emergency_plan.router, prefix="/api", tags=["emergency-plan"])
app.include_router(care_notes.router, prefix="/api", tags=["care-notes"])
app.include_router(carer_updates.router, prefix="/api", tags=["carer-updates"])
app.include_router(intake_forms.router, prefix="/api", tags=["intake-forms"])
app.include_router(handouts.router, prefix="/api", tags=["handouts"])
app.include_router(expenses.router, prefix="/api", tags=["expenses"])
app.include_router(diary.router, prefix="/api", tags=["diary"])
app.include_router(calendar.router, prefix="/api", tags=["calendar"])
app.include_router(groups.router, prefix="/api", tags=["groups"])
app.include_router(medications.router, prefix="/api", tags=["medications"])
app.include_router(conditions.router, prefix="/api", tags=["conditions"])
app.include_router(access.router, prefix="/api", tags=["access"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(organization.router, prefix="/api", tags=["organization"])
app.include_router(correspondents.router, prefix="/api", tags=["correspondents"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(sharing.router, prefix="/api", tags=["sharing"])
app.include_router(share_links.router, prefix="/api", tags=["share-links"])
if settings.is_dev:
    app.include_router(dev.router, prefix="/api/dev", tags=["dev"])


@app.get("/health")
async def health():
    """Readiness: does this instance actually work?

    It used to return a static "ok" and check nothing — so when Postgres died,
    the healthcheck still passed and nobody noticed (#115). Probes the two
    dependencies without which the app is a shell.
    """
    from sqlalchemy import text

    checks: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        try:
            await r.ping()
        finally:
            await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content={"status": "degraded", "checks": checks})
    return {"status": "ok", "checks": checks}


@app.get("/alive")
async def alive():
    return {"status": "alive"}
