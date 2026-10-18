import asyncio
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.log_handler import REDIS_CHANNEL, get_log_history
from app.deps import get_current_user, operator_only, require_admin
from app.models.audit import AuditLog
from app.models.document import DocumentReference
from app.models.log_entry import LogEntry
from app.models.group import Group, GroupMembership
from app.models.organization import Organization
from app.models.system import SystemSetting, UserInvitation
from app.models.user import User, UserRole
from app.schemas.admin import (
    AiModelConfigRequest,
    AdminGroupDto,
    AdminGroupMemberDto,
    AdminUserDto,
    AuditLogDto,
    CreateInvitationRequest,
    InvitationDto,
    DataCategoryDto,
    LicenseDto,
    OllamaConnectionTestResult,
    OllamaModelInfo,
    OllamaPullRequest,
    OllamaPullStatus,
    OllamaSettingsDto,
    PipelineTaskDto,
    TaskRunDto,
    SetUserActiveRequest,
    UpdateDataCategoryRequest,
    UpdateUserRoleRequest,
    UploadLicenseRequest,
)
from app.schemas.common import PagedResult
from app.schemas.erasure import EraseUserRequest

router = APIRouter()

_pull_status: dict[str, OllamaPullStatus] = {}


def _get_app_version() -> str:
    try:
        import tomllib
        with open("/app/pyproject.toml", "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        try:
            from importlib.metadata import version
            return version("openavisio")
        except Exception:
            return "unknown"


def _get_commit_hash() -> str:
    import os
    return os.environ.get("GIT_COMMIT", "unknown")


@router.get("/users", response_model=list[AdminUserDto])
async def list_users(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.is_deleted == False))  # noqa: E712
    return result.scalars().all()


@router.post("/users/{user_id}/role")
async def set_user_role(user_id: uuid.UUID, body: UpdateUserRoleRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))  # noqa: E712
    target = result.scalar_one_or_none()
    if not target:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    target.role = body.role
    await db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/erase", status_code=status.HTTP_204_NO_CONTENT)
async def erase_user(
    user_id: uuid.UUID,
    body: EraseUserRequest,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import UserRole
    from app.services.erasure import erase_user as _erase

    # Allow admin or self-erasure only
    if actor.role != UserRole.admin and actor.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    result = await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))  # noqa: E712
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if body.confirm_email.strip() != target.email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Confirmation email does not match.")

    await _erase(user_id, actor, db)


@router.post("/users/{user_id}/active")
async def set_user_active(user_id: uuid.UUID, body: SetUserActiveRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))  # noqa: E712
    target = result.scalar_one_or_none()
    if not target:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    target.is_active = body.is_active
    await db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/remove")
async def remove_member(user_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Take a member out (ADR 052): no login, no access to any Patient; what they wrote stays theirs."""
    from app.models.access import PatientAccess
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove yourself.")
    target = (await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    target.is_active = False
    now = datetime.now(UTC)
    active = lambda: (PatientAccess.revoked_at == None, PatientAccess.is_deleted == False)  # noqa: E711, E712, E731
    grants = (await db.execute(select(PatientAccess).where(PatientAccess.user_id == user_id, *active()))).scalars().all()
    for g in grants:
        g.revoked_at = now
    await db.flush()
    # a Patient whose only admin-level grant just went is handed to whoever removed them
    for pid in {g.patient_id for g in grants if g.access_level == "admin"}:
        if await db.scalar(select(func.count()).select_from(PatientAccess).where(
                PatientAccess.patient_id == pid, PatientAccess.access_level == "admin", *active())):
            continue
        own = (await db.execute(select(PatientAccess).where(
            PatientAccess.patient_id == pid, PatientAccess.user_id == admin.id, *active()))).scalars().first()
        if own:
            own.access_level = "admin"
        else:
            db.add(PatientAccess(patient_id=pid, user_id=admin.id, access_level="admin",
                                 granted_by_user_id=admin.id, granted_at=now))
    await db.commit()
    return {"ok": True}


@router.get("/groups", response_model=list[AdminGroupDto])
async def list_groups(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.is_deleted == False))  # noqa: E712
    return result.scalars().all()


@router.get("/groups/{group_id}/members", response_model=list[AdminGroupMemberDto])
async def list_group_members(group_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GroupMembership).where(GroupMembership.group_id == group_id, GroupMembership.is_deleted == False))  # noqa: E712
    return result.scalars().all()


@router.get("/invitations", response_model=list[InvitationDto])
async def list_invitations(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserInvitation))
    return result.scalars().all()


@router.post("/invitations", response_model=InvitationDto, status_code=201)
async def create_invitation(body: CreateInvitationRequest, background_tasks: BackgroundTasks, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from app.services.license import PERSONAL_USER_LIMIT, Tier, get_license_info
    info = await get_license_info(db, settings.license_public_key)
    if info.tier == Tier.personal:
        count = await db.scalar(
            select(func.count()).select_from(User).where(User.is_active == True)  # noqa: E712
        )
        if count >= PERSONAL_USER_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Personal tier is limited to {PERSONAL_USER_LIMIT} users. "
                       "For unlimited users, obtain a Commercial License at openavisio.org.",
            )
    token = secrets.token_urlsafe(32)
    inv = UserInvitation(email=body.email, token=token, expires_at=datetime.now(UTC) + timedelta(days=7), created_by_user_id=admin.id)
    db.add(inv)
    await db.commit()
    await db.refresh(inv)

    from app.services.email import send_invitation_email
    background_tasks.add_task(send_invitation_email, body.email, token)

    return inv


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(invitation_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    inv = await db.get(UserInvitation, invitation_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if inv.is_used:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This invitation was already accepted.")
    await db.delete(inv)
    await db.commit()


@router.get("/audit", response_model=PagedResult[AuditLogDto])
async def get_audit_log(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    if user_id:
        q = q.where(AuditLog.user_id == user_id)
    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    q = q.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()
    return PagedResult(items=items, total=total, page=page, page_size=page_size)


_AI_MODEL_KEYS = ("extract", "classify", "chat", "vision")


async def _get_ai_model_settings(db: AsyncSession) -> dict[str, str | None]:
    rows = await db.execute(
        select(SystemSetting).where(SystemSetting.key.in_([f"ai.model.{s}" for s in _AI_MODEL_KEYS]))
    )
    return {row.key.removeprefix("ai.model."): row.value for row in rows.scalars().all()}


@router.get("/ollama", dependencies=[Depends(operator_only)], response_model=OllamaSettingsDto)
async def get_ollama_settings(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    model_settings = await _get_ai_model_settings(db)

    models: list[OllamaModelInfo] = []
    connected = False
    ollama_url: str | None = None
    backend_type: str | None = None
    try:
        async with httpx.AsyncClient(timeout=5, headers=settings.ai_service_headers) as client:
            resp = await client.get(f"{settings.ai_service_url}/models")
            if resp.status_code == 200:
                connected = True
                data = resp.json()
                ollama_url = data.get("ollama_url")
                backend_type = data.get("backend")
                for m in data.get("models", []):
                    models.append(OllamaModelInfo(
                        name=m.get("name", ""),
                        size=m.get("size"),
                        modified_at=m.get("modified_at"),
                        tasks=m.get("tasks", []),
                        hint=m.get("hint"),
                        tags=m.get("tags", []),
                    ))
    except Exception:
        pass

    current = {k: model_settings.get(k) for k in _AI_MODEL_KEYS}
    return OllamaSettingsDto(
        backend=settings.ai_service_url,
        backend_type=backend_type,
        connected=connected,
        url=ollama_url,
        models=models,
        embed_model=None,
        classify_model=current.get("classify"),
        extract_model=current.get("extract"),
        vision_model=current.get("vision"),
        chat_model=current.get("chat"),
        current_models=current,
    )


@router.put("/ollama/models", dependencies=[Depends(operator_only)])
async def save_ai_model_config(
    body: AiModelConfigRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    for stage, value in {
        "extract": body.extract_model,
        "classify": body.classify_model,
        "chat": body.chat_model,
        "vision": body.vision_model,
    }.items():
        if value is not None:
            stmt = pg_insert(SystemSetting).values(key=f"ai.model.{stage}", value=value)
            stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value})
            await db.execute(stmt)
    await db.commit()
    return {"ok": True}


@router.post("/ollama/test", dependencies=[Depends(operator_only)], response_model=OllamaConnectionTestResult)
async def test_ollama(admin: User = Depends(require_admin)):
    try:
        async with httpx.AsyncClient(timeout=5, headers=settings.ai_service_headers) as client:
            resp = await client.get(f"{settings.ai_service_url}/health")
            if resp.status_code == 200:
                return OllamaConnectionTestResult(success=True, message="AI service reachable")
    except Exception as e:
        return OllamaConnectionTestResult(success=False, message=str(e))
    return OllamaConnectionTestResult(success=False, message="Unexpected response")


@router.post("/ollama/pull", dependencies=[Depends(operator_only)])
async def pull_model(body: OllamaPullRequest, admin: User = Depends(require_admin)):
    _pull_status[body.model] = OllamaPullStatus(status="pulling", progress=0)
    try:
        async with httpx.AsyncClient(timeout=5, headers=settings.ai_service_headers) as client:
            await client.post(f"{settings.ai_service_url}/models/pull", json={"model": body.model})
    except Exception:
        pass
    return {"ok": True}


@router.get("/ollama/pull/status", dependencies=[Depends(operator_only)])
async def get_pull_status(admin: User = Depends(require_admin)):
    return _pull_status


@router.get("/logs/tasks", dependencies=[Depends(operator_only)], response_model=list[PipelineTaskDto])
async def get_pipeline_tasks(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DocumentReference)
        .options(selectinload(DocumentReference.patient))
        .where(DocumentReference.is_deleted == False)  # noqa: E712
        .order_by(DocumentReference.updated_at.desc())
        .limit(50)
    )
    docs = result.scalars().all()
    return [
        PipelineTaskDto(
            id=doc.id,
            file_name=doc.file_name,
            patient_name=f"{doc.patient.given_name} {doc.patient.family_name}" if doc.patient else "Unknown",
            processing_status=doc.processing_status,
            pipeline_stage=doc.pipeline_stage,
            processing_error=doc.processing_error,
            updated_at=doc.updated_at,
        )
        for doc in docs
    ]


@router.get("/logs/task-runs", dependencies=[Depends(operator_only)], response_model=list[TaskRunDto])
async def get_task_runs(
    task_status: str | None = Query(None, alias="status"),
    name: str | None = Query(None),
    limit: int = Query(100, le=500),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.models.task_run import TaskRun

    q = select(TaskRun).order_by(TaskRun.created_at.desc()).limit(limit)
    if task_status:
        q = q.where(TaskRun.status == task_status)
    if name:
        q = q.where(TaskRun.task_name == name)
    return (await db.execute(q)).scalars().all()


# --- GDPR data governance (#15/#16) ------------------------------------------

@router.get("/data-categories", dependencies=[Depends(operator_only)], response_model=list[DataCategoryDto])
async def list_data_categories(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from app.models.governance import DataCategory
    from app.services.governance import ensure_categories_seeded

    await ensure_categories_seeded(db)
    result = await db.execute(select(DataCategory).order_by(DataCategory.label))
    return result.scalars().all()


@router.put("/data-categories/{code}", dependencies=[Depends(operator_only)], response_model=DataCategoryDto)
async def update_data_category(
    code: str,
    body: UpdateDataCategoryRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.models.governance import DataCategory
    from app.services.governance import LAWFUL_BASES

    if body.lawful_basis is not None and body.lawful_basis not in LAWFUL_BASES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown lawful basis.")
    if body.retention_days is not None and body.retention_days < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="retention_days must be >= 1.")

    cat = (await db.execute(select(DataCategory).where(DataCategory.code == code))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    cat.lawful_basis = body.lawful_basis
    cat.retention_days = body.retention_days
    name = " ".join(filter(None, [admin.first_name, admin.last_name])) or admin.email
    db.add(AuditLog(
        timestamp=datetime.now(UTC), user_id=admin.id, user_name=name,
        entity_type="DataCategory", entity_id=code, action="updated",
        changes={"lawful_basis": body.lawful_basis, "retention_days": body.retention_days},
    ))
    await db.commit()
    await db.refresh(cat)
    return cat


@router.get("/logs/history", dependencies=[Depends(operator_only)])
async def get_log_history_db(
    level: str | None = Query(None),
    source: str | None = Query(None),
    limit: int = Query(500, le=2000),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(LogEntry).order_by(LogEntry.timestamp.desc()).limit(limit)
    if level:
        q = q.where(LogEntry.level == level.upper())
    if source:
        q = q.where(LogEntry.source == source)
    rows = (await db.execute(q)).scalars().all()
    return [
        {"ts": r.timestamp.isoformat(), "level": r.level, "logger": r.logger, "msg": r.message, "source": r.source, "exc": r.exc}
        for r in reversed(rows)
    ]


@router.get("/logs/stream", dependencies=[Depends(operator_only)])
async def stream_logs(
    admin: User = Depends(require_admin),
):
    async def generate():
        import redis.asyncio as aioredis

        client = aioredis.Redis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(REDIS_CHANNEL)
        loop = asyncio.get_running_loop()
        last_ping = loop.time()
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    yield f"data: {msg['data']}\n\n"
                now = loop.time()
                if now - last_ping > 15.0:
                    yield ": ping\n\n"
                    last_ping = now
        except GeneratorExit:
            pass
        finally:
            await pubsub.unsubscribe(REDIS_CHANNEL)
            await client.aclose()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/system", dependencies=[Depends(operator_only)])
async def get_system_info(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    import os
    import platform
    import sys
    import time

    import fastapi
    import pydantic
    import redis.asyncio as aioredis
    from sqlalchemy import text

    from app.models.document import DocumentReference
    from app.models.patient import Patient

    # Counts
    user_count = (await db.execute(select(User).where(User.is_deleted == False))).scalars().all()  # noqa: E712
    patient_count = (await db.execute(select(Patient).where(Patient.is_deleted == False))).scalars().all()  # noqa: E712
    doc_count = (await db.execute(select(DocumentReference).where(DocumentReference.is_deleted == False))).scalars().all()  # noqa: E712

    # PostgreSQL version + db size
    pg_version_row = (await db.execute(text("SELECT version()"))).scalar()
    db_size_row = (await db.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))"))).scalar()
    table_count_row = (await db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"))).scalar()

    # Redis info
    redis_info: dict = {}
    try:
        rc = aioredis.Redis.from_url(settings.redis_url, decode_responses=True)
        info = await rc.info()
        await rc.aclose()
        redis_info = {
            "version": info.get("redis_version"),
            "used_memory_human": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "uptime_in_seconds": info.get("uptime_in_seconds"),
        }
    except Exception:
        pass

    # Disk usage for document storage
    disk: dict = {}
    try:
        st = os.statvfs(settings.document_storage_path)
        total = st.f_frsize * st.f_blocks
        free = st.f_frsize * st.f_bavail
        used = total - free
        def fmt(b: int) -> str:
            for unit in ("B", "KB", "MB", "GB", "TB"):
                if b < 1024:
                    return f"{b:.1f} {unit}"
                b //= 1024
            return f"{b:.1f} TB"
        disk = {"total": fmt(total), "used": fmt(used), "free": fmt(free), "pct": round(used / total * 100, 1) if total else 0}
    except Exception:
        pass

    # Process uptime
    process_start = time.time() - (time.monotonic() - 0)
    try:
        with open(f"/proc/{os.getpid()}/stat") as f:
            parts = f.read().split()
            hz = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
            with open("/proc/uptime") as uf:
                uptime_sec = float(uf.read().split()[0])
            start_ticks = int(parts[21])
            proc_uptime_sec = uptime_sec - (start_ticks / hz)
            h, rem = divmod(int(proc_uptime_sec), 3600)
            m, s = divmod(rem, 60)
            process_uptime = f"{h}h {m}m {s}s"
    except Exception:
        process_uptime = "unknown"

    return {
        "runtime": {
            "app_version": _get_app_version(),
            "commit": _get_commit_hash(),
            "python_version": sys.version.split()[0],
            "platform": platform.system() + " " + platform.release(),
            "fastapi_version": fastapi.__version__,
            "pydantic_version": pydantic.__version__,
            "process_uptime": process_uptime,
            "pid": os.getpid(),
        },
        "database": {
            "version": pg_version_row,
            "size": db_size_row,
            "tables": table_count_row,
        },
        "redis": redis_info,
        "storage": disk,
        "counts": {
            "users": len(user_count),
            "patients": len(patient_count),
            "documents": len(doc_count),
        },
    }


def _to_license_dto(info) -> LicenseDto:
    return LicenseDto(
        tier=info.tier.value,
        has_license=info.has_license,
        is_grace_period=info.is_grace_period,
        issued_to=info.issued_to,
        expires_at=info.expires_at,
        grace_ends_at=info.grace_ends_at,
    )


@router.get("/license", dependencies=[Depends(operator_only)], response_model=LicenseDto)
async def get_license(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from app.services.license import get_license_info
    info = await get_license_info(db, settings.license_public_key)
    return _to_license_dto(info)


@router.post("/license", dependencies=[Depends(operator_only)], response_model=LicenseDto)
async def upload_license(
    body: UploadLicenseRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.license import _DEFAULT_PUBLIC_KEY_B64, decode_license, get_license_info

    key = settings.license_public_key.strip() or _DEFAULT_PUBLIC_KEY_B64
    try:
        decode_license(body.token.strip(), key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    result = await db.execute(select(Organization))
    org = result.scalar_one()
    org.license_token = body.token.strip()
    await db.commit()

    info = await get_license_info(db, settings.license_public_key)
    return _to_license_dto(info)


@router.delete("/license", dependencies=[Depends(operator_only)], status_code=status.HTTP_204_NO_CONTENT)
async def delete_license(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization))
    org = result.scalar_one()
    org.license_token = None
    await db.commit()


# ---------------------------------------------------------------------------
# Notification settings
# ---------------------------------------------------------------------------

# field -> default; stored under notify.<field>
_NOTIFY = {
    "event_reminder": True,
    "caregiver_added": True,
    "invitation": True,
    "include_content": False,  # #251: no health data in mails unless an admin decides so
}


async def _get_notify_settings(db) -> dict:
    from app.models.system import SystemSetting
    result = await db.execute(select(SystemSetting).where(SystemSetting.key.in_([f"notify.{f}" for f in _NOTIFY])))
    cfg = {s.key: s.value for s in result.scalars().all()}
    return {f: (cfg.get(f"notify.{f}") or str(default)).lower() == "true" for f, default in _NOTIFY.items()}


async def _upsert_notify(db, key: str, value: bool) -> None:
    from app.models.system import SystemSetting
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = "true" if value else "false"
    else:
        db.add(SystemSetting(key=key, value="true" if value else "false"))


@router.get("/notification-settings")
async def get_notification_settings(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _get_notify_settings(db)


@router.put("/notification-settings")
async def update_notification_settings(
    body: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    for field in _NOTIFY:
        if field in body:
            await _upsert_notify(db, f"notify.{field}", bool(body[field]))
    await db.commit()
    return await _get_notify_settings(db)
