import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.diary import DiaryEntry, DiaryTemplate
from app.models.user import User
from app.schemas.diary import (
    DiaryEntryCreateRequest,
    DiaryEntryDto,
    DiaryEntryUpdateRequest,
    DiaryTemplateCreateRequest,
    DiaryTemplateDto,
    DiaryTemplateUpdateRequest,
)

router = APIRouter()

# Free-text note fields encrypted under the patient KEK (ADR-031); structured
# fields (mood, pain, dates) stay plaintext so they remain queryable.
_NOTE_FIELDS = ("general_notes", "nutrition_notes")


async def _seal(entry: DiaryEntry, db: AsyncSession) -> None:
    """Encrypt plaintext note fields in place before persisting a new entry."""
    from app.core.encryption import encrypt_str
    from app.core.patient_keys import ensure_patient_kek
    kek = None
    for f in _NOTE_FIELDS:
        v = getattr(entry, f)
        if v:
            kek = kek or await ensure_patient_kek(db, entry.patient_id)
            setattr(entry, f, encrypt_str(v, kek))


async def _reveal(entries: list[DiaryEntry], db: AsyncSession) -> list[DiaryEntry]:
    """Decrypt note fields in place for serialization. Last step before return."""
    from app.core.encryption import decrypt_str
    from app.core.patient_keys import get_patient_kek
    keks: dict = {}
    for e in entries:
        if not any(getattr(e, f) for f in _NOTE_FIELDS):
            continue
        if e.patient_id not in keks:
            keks[e.patient_id] = await get_patient_kek(db, e.patient_id)
        for f in _NOTE_FIELDS:
            v = getattr(e, f)
            if v:
                setattr(e, f, decrypt_str(v, keks[e.patient_id]))
    return entries


@router.get("/patients/{patient_id}/diary", response_model=list[DiaryEntryDto])
async def list_diary(
    patient_id: uuid.UUID,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = select(DiaryEntry).where(DiaryEntry.patient_id == patient_id, DiaryEntry.is_deleted == False)  # noqa: E712
    if from_:
        q = q.where(DiaryEntry.entry_date >= from_)
    if to:
        q = q.where(DiaryEntry.entry_date <= to)
    result = await db.execute(q.order_by(DiaryEntry.entry_date.desc()))
    return await _reveal(list(result.scalars().all()), db)


@router.get("/patients/{patient_id}/diary/{date}", response_model=list[DiaryEntryDto])
async def list_diary_by_date(
    patient_id: uuid.UUID,
    date: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(select(DiaryEntry).where(
        DiaryEntry.patient_id == patient_id,
        DiaryEntry.entry_date == date,
        DiaryEntry.is_deleted == False,  # noqa: E712
    ))
    return await _reveal(list(result.scalars().all()), db)


@router.post("/patients/{patient_id}/diary", response_model=DiaryEntryDto, status_code=status.HTTP_201_CREATED)
async def create_diary_entry(
    patient_id: uuid.UUID,
    body: DiaryEntryCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    entry = DiaryEntry(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    await _seal(entry, db)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return (await _reveal([entry], db))[0]


@router.get("/diary/{entry_id}", response_model=DiaryEntryDto)
async def get_diary_entry(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DiaryEntry).where(DiaryEntry.id == entry_id, DiaryEntry.is_deleted == False))  # noqa: E712
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(entry.patient_id, user, db)
    return (await _reveal([entry], db))[0]


@router.put("/diary/{entry_id}", response_model=DiaryEntryDto)
async def update_diary_entry(
    entry_id: uuid.UUID,
    body: DiaryEntryUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DiaryEntry).where(DiaryEntry.id == entry_id, DiaryEntry.is_deleted == False))  # noqa: E712
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(entry.patient_id, user, db, AccessLevel.contribute)
    updates = body.model_dump(exclude_none=True)
    # fetch the KEK while `entry` is still clean, so no plaintext note is flushed
    # before we re-encrypt it (ADR-031)
    touched = [f for f in _NOTE_FIELDS if updates.get(f)]
    from app.core.encryption import encrypt_str
    from app.core.patient_keys import ensure_patient_kek
    kek = await ensure_patient_kek(db, entry.patient_id) if touched else None
    for field, value in updates.items():
        setattr(entry, field, value)
    for f in touched:  # untouched note fields keep their existing ciphertext
        setattr(entry, f, encrypt_str(getattr(entry, f), kek))
    await db.commit()
    await db.refresh(entry)
    return (await _reveal([entry], db))[0]


@router.delete("/diary/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diary_entry(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DiaryEntry).where(DiaryEntry.id == entry_id, DiaryEntry.is_deleted == False))  # noqa: E712
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(entry.patient_id, user, db, AccessLevel.contribute)
    entry.is_deleted = True
    await db.commit()


# --- Templates ---

@router.get("/patients/{patient_id}/diary/templates", response_model=list[DiaryTemplateDto])
async def list_templates(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(select(DiaryTemplate).where(
        DiaryTemplate.patient_id == patient_id,
        DiaryTemplate.is_deleted == False,  # noqa: E712
    ))
    return result.scalars().all()


@router.post("/patients/{patient_id}/diary/templates", response_model=DiaryTemplateDto, status_code=status.HTTP_201_CREATED)
async def create_template(
    patient_id: uuid.UUID,
    body: DiaryTemplateCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    tmpl = DiaryTemplate(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


@router.put("/diary/templates/{template_id}", response_model=DiaryTemplateDto)
async def update_template(
    template_id: uuid.UUID,
    body: DiaryTemplateUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DiaryTemplate).where(DiaryTemplate.id == template_id, DiaryTemplate.is_deleted == False))  # noqa: E712
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(tmpl.patient_id, user, db, AccessLevel.contribute)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(tmpl, field, value)
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


@router.delete("/diary/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DiaryTemplate).where(DiaryTemplate.id == template_id, DiaryTemplate.is_deleted == False))  # noqa: E712
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(tmpl.patient_id, user, db, AccessLevel.contribute)
    tmpl.is_deleted = True
    await db.commit()
