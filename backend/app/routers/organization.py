import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import encrypt_setting
from app.core.security import generate_recovery_code, hash_password, normalize_recovery_code
from app.deps import get_current_user, require_admin
from app.models.organization import Organization
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.system import SystemSetting
from app.models.user import User, UserRole
from app.schemas.organization import (
    OrganizationDto,
    OrganizationInitRequest,
    OrganizationInitResponse,
    OrganizationUpdateRequest,
)

router = APIRouter()


async def _get_org(db: AsyncSession) -> Organization | None:
    result = await db.execute(select(Organization))
    return result.scalar_one_or_none()


# Setting keys whose values are secrets and must be encrypted at rest.
_SECRET_SETTING_KEYS = {"smtp.password", "ai.api_key"}


async def _upsert_setting(db: AsyncSession, key: str, value: str | None) -> None:
    if value is not None and key in _SECRET_SETTING_KEYS and settings.document_encryption_key:
        value = encrypt_setting(value)
    stmt = pg_insert(SystemSetting).values(key=key, value=value)
    stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value})
    await db.execute(stmt)


@router.get("/organization/status")
async def organization_status(db: AsyncSession = Depends(get_db)):
    org = await _get_org(db)
    return {
        "initialized": org is not None,
        "default_language": org.default_language if org else "en",
    }


@router.get("/organization", response_model=OrganizationDto)
async def get_organization(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org = await _get_org(db)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return org


@router.post("/organization/init", response_model=OrganizationInitResponse, status_code=status.HTTP_201_CREATED)
async def init_organization(
    body: OrganizationInitRequest,
    db: AsyncSession = Depends(get_db),
    x_bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
):
    # In production, first-run setup must present the bootstrap token that
    # setup.sh generated, so an attacker can't seize admin during the deploy
    # window. Dev/test skip this to keep the wizard and tests zero-config.
    if not settings.is_dev:
        if not settings.bootstrap_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Setup is disabled: BOOTSTRAP_TOKEN is not configured on the server",
            )
        if not x_bootstrap_token or not secrets.compare_digest(x_bootstrap_token, settings.bootstrap_token):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing bootstrap token")

    existing = await _get_org(db)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organization already initialized")

    # ADR 044: a household has one admin and nobody to ask. The code is shown
    # once, in the response to this call, and never again.
    recovery_code = generate_recovery_code()
    admin = User(
        email=body.admin_email,
        hashed_password=hash_password(body.admin_password),
        recovery_code_hash=hash_password(normalize_recovery_code(recovery_code)),
        first_name=body.admin_first_name,
        last_name=body.admin_last_name,
        role=UserRole.admin,
        is_active=True,
        email_confirmed=True,
    )
    db.add(admin)
    await db.flush()
    valid_locales = ("de", "en")
    org = Organization(
        name=body.name,
        description=body.description,
        default_language=body.locale if body.locale in valid_locales else "en",
        is_household=body.is_household,
    )
    db.add(org)

    if body.smtp:
        s = body.smtp
        for key, val in [
            ("smtp.host", s.host),
            ("smtp.port", str(s.port)),
            ("smtp.user", s.user),
            ("smtp.password", s.password),
            ("smtp.from", s.from_address),
        ]:
            await _upsert_setting(db, key, val)

    if body.ai:
        a = body.ai
        for key, val in [
            ("ai.backend", a.backend),
            ("ai.url", a.url),
            ("ai.model", a.model),
            ("ai.api_key", a.api_key),
        ]:
            await _upsert_setting(db, key, val)

    if body.first_patient:
        p = body.first_patient
        patient = Patient(
            given_name=p.given_name,
            family_name=p.family_name,
            birth_date=p.birth_date,
            created_by=admin.id,
        )
        db.add(patient)
        await db.flush()
        db.add(PatientAccess(
            patient_id=patient.id, user_id=admin.id, access_level="admin",
            granted_by_user_id=admin.id, granted_at=datetime.now(UTC),
        ))

    await db.commit()
    await db.refresh(org)
    return OrganizationInitResponse(
        **OrganizationDto.model_validate(org).model_dump(), recovery_code=recovery_code
    )


@router.put("/organization", response_model=OrganizationDto)
async def update_organization(body: OrganizationUpdateRequest, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    org = await _get_org(db)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    # exclude_unset, not exclude_none: an admin must be able to CLEAR a field by
    # sending null — with exclude_none a wrong VAT ID could never be removed.
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    await db.commit()
    await db.refresh(org)
    return org
