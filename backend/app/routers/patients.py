import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.storage import get_storage
from app.deps import get_current_user, require_manager
from app.models.access import PatientAccess
from app.models.favorite import PatientFavorite
from app.models.patient import Patient
from app.models.user import User
from app.schemas.erasure import ErasePatientRequest
from app.schemas.patient import PatientCreateRequest, PatientDto, PatientUpdateRequest
from app.services.license import PERSONAL_PATIENT_LIMIT, Tier, get_license_info

router = APIRouter()


async def _favorite_ids(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await db.execute(
        select(PatientFavorite.patient_id).where(
            PatientFavorite.user_id == user_id, PatientFavorite.is_deleted == False  # noqa: E712
        )
    )
    return {r[0] for r in rows}


def _to_dto(p: Patient, favs: set[uuid.UUID]) -> PatientDto:
    dto = PatientDto.model_validate(p)
    dto.is_favorite = p.id in favs
    dto.has_photo = bool(p.photo_storage_path)
    return dto


@router.get("/patients", response_model=list[PatientDto])
async def list_patients(
    q: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.access import resolve_patient_access
    result = await db.execute(select(Patient).where(Patient.is_deleted == False))  # noqa: E712
    all_patients = result.scalars().all()
    favs = await _favorite_ids(db, user.id)
    accessible = []
    for p in all_patients:
        level = await resolve_patient_access(p.id, user, db)
        if level is not None:
            if not q or q.lower() in f"{p.given_name} {p.family_name}".lower() or (p.identifier and q.lower() in p.identifier.lower()):
                accessible.append(_to_dto(p, favs))
    return accessible


@router.get("/patients/favorites", response_model=list[PatientDto])
async def list_favorite_patients(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accessible favorite patients (for the sidebar). Revoked access drops them."""
    from app.auth.access import resolve_patient_access
    favs = await _favorite_ids(db, user.id)
    if not favs:
        return []
    result = await db.execute(select(Patient).where(Patient.id.in_(favs), Patient.is_deleted == False))  # noqa: E712
    out = []
    for p in result.scalars().all():
        if await resolve_patient_access(p.id, user, db) is not None:
            out.append(_to_dto(p, favs))
    return out


@router.put("/patients/{patient_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.access import require_patient_access
    await require_patient_access(patient_id, user, db)
    existing = await db.execute(
        select(PatientFavorite).where(
            PatientFavorite.user_id == user.id, PatientFavorite.patient_id == patient_id,
            PatientFavorite.is_deleted == False,  # noqa: E712
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(PatientFavorite(user_id=user.id, patient_id=patient_id))
        await db.commit()


@router.delete("/patients/{patient_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PatientFavorite).where(
            PatientFavorite.user_id == user.id, PatientFavorite.patient_id == patient_id,
        )
    )
    for fav in result.scalars().all():
        await db.delete(fav)
    await db.commit()


@router.get("/patients/{patient_id}", response_model=PatientDto)
async def get_patient(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.access import require_patient_access
    await require_patient_access(patient_id, user, db)
    result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False))  # noqa: E712
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    favs = await _favorite_ids(db, user.id)
    return _to_dto(patient, favs)


# --- Photo (optional, encrypted PHI — ADR-031) -------------------------------

_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}  # raster only — no SVG (in-origin script risk)
_PHOTO_MAX = 8 * 1024 * 1024


async def _get_patient_or_404(patient_id: uuid.UUID, db: AsyncSession) -> Patient:
    p = (await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return p


@router.post("/patients/{patient_id}/photo", response_model=PatientDto)
async def upload_patient_photo(
    patient_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.core.config import settings
    if settings.demo_locked_upload_sha256:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="This is a public demo — photo upload is disabled.")
    from app.auth.access import AccessLevel, require_patient_access
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    patient = await _get_patient_or_404(patient_id, db)
    if file.content_type not in _PHOTO_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Only JPEG, PNG or WebP images are allowed.")
    data = await file.read()
    if len(data) > _PHOTO_MAX:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="Image too large (max 8 MB).")

    from app.core.encryption import encrypt_document
    from app.core.patient_keys import ensure_patient_kek
    kek = await ensure_patient_kek(db, patient_id)
    ciphertext, wrapped_dek = encrypt_document(data, kek)
    key = f"{patient_id}/photo.enc"  # same per-patient dir as documents (writable), stable key
    get_storage().write(key, ciphertext)
    patient.photo_storage_path = key
    patient.photo_dek = wrapped_dek
    patient.photo_content_type = file.content_type
    await db.commit()
    return _to_dto(patient, await _favorite_ids(db, user.id))


@router.get("/patients/{patient_id}/photo")
async def get_patient_photo(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.access import require_patient_access
    await require_patient_access(patient_id, user, db)
    patient = await _get_patient_or_404(patient_id, db)
    if not patient.photo_storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    from app.core.encryption import decrypt_document
    from app.core.patient_keys import get_patient_kek
    kek = await get_patient_kek(db, patient_id)
    data = decrypt_document(get_storage().read(patient.photo_storage_path), patient.photo_dek, kek)
    from fastapi.responses import Response
    return Response(
        content=data,
        media_type=patient.photo_content_type or "image/jpeg",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=60"},
    )


@router.delete("/patients/{patient_id}/photo", response_model=PatientDto)
async def delete_patient_photo(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.access import AccessLevel, require_patient_access
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    patient = await _get_patient_or_404(patient_id, db)
    if patient.photo_storage_path:
        try:
            get_storage().delete(patient.photo_storage_path)
        except Exception:
            pass  # best-effort; clearing the row is what matters
        patient.photo_storage_path = None
        patient.photo_dek = None
        patient.photo_content_type = None
        await db.commit()
    return _to_dto(patient, await _favorite_ids(db, user.id))


@router.post("/patients", response_model=PatientDto, status_code=status.HTTP_201_CREATED)
async def create_patient(
    body: PatientCreateRequest,
    user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    info = await get_license_info(db, settings.license_public_key)
    if info.tier == Tier.personal:
        count = await db.scalar(
            select(func.count()).select_from(Patient).where(Patient.is_deleted == False)  # noqa: E712
        )
        if count >= PERSONAL_PATIENT_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Personal tier is limited to 10 patients. "
                       "For unlimited patients, obtain a Commercial License at openavisio.org.",
            )

    patient = Patient(
        created_by=user.id,
        given_name=body.given_name,
        family_name=body.family_name,
        birth_date=body.birth_date,
        gender=body.gender,
        identifier=body.identifier,
    )
    db.add(patient)
    await db.flush()
    # creator gets a normal, revocable admin grant instead of ownership (ADR 026)
    db.add(PatientAccess(
        patient_id=patient.id,
        user_id=user.id,
        access_level="admin",
        granted_by_user_id=user.id,
        granted_at=datetime.now(UTC),
    ))
    await db.commit()
    await db.refresh(patient)
    return patient


@router.put("/patients/{patient_id}", response_model=PatientDto)
async def update_patient(
    patient_id: uuid.UUID,
    body: PatientUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.access import AccessLevel, require_patient_access
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False))  # noqa: E712
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(patient, field, value)
    await db.commit()
    await db.refresh(patient)
    return patient


@router.delete("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.access import AccessLevel, require_patient_access
    await require_patient_access(patient_id, user, db, AccessLevel.full)
    result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False))  # noqa: E712
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    patient.is_deleted = True
    await db.commit()


@router.post("/patients/{patient_id}/erase", status_code=status.HTTP_204_NO_CONTENT)
async def erase_patient(
    patient_id: uuid.UUID,
    body: ErasePatientRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.access import AccessLevel, require_patient_access
    from app.services.erasure import erase_patient as _erase

    await require_patient_access(patient_id, user, db, AccessLevel.admin)

    result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False))  # noqa: E712
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    expected = f"{patient.given_name} {patient.family_name}"
    if body.confirm_name.strip() != expected:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Confirmation name does not match.")

    await _erase(patient_id, user, db)
