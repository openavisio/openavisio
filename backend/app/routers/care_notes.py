import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.care_notes import HEADINGS, CareNotes
from app.models.user import User
from app.schemas.care_notes import CareNotesDto, CareNotesIn

router = APIRouter()


async def _notes_of(patient_id, db) -> CareNotes | None:
    return (await db.execute(select(CareNotes).where(CareNotes.patient_id == patient_id))).scalar_one_or_none()


@router.get("/patients/{patient_id}/care-notes", response_model=CareNotesDto | None)
async def get_care_notes(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    return await _notes_of(patient_id, db)


@router.put("/patients/{patient_id}/care-notes", response_model=CareNotesDto)
async def save_care_notes(
    patient_id: uuid.UUID,
    body: CareNotesIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    notes = await _notes_of(patient_id, db)
    if not notes:
        notes = CareNotes(patient_id=patient_id, owner_id=user.id)
        db.add(notes)
    for h in HEADINGS:
        setattr(notes, h, (getattr(body, h) or "").strip() or None)
    await db.commit()
    await db.refresh(notes)
    return notes
