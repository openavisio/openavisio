"""Intake Forms and History Facts (ADR 047)."""

import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.core.encryption import decrypt_document, encrypt_document, encrypt_str
from app.core.patient_keys import ensure_patient_kek, get_patient_kek
from app.core.storage import get_storage
from app.deps import get_current_user
from app.models.intake import HistoryFact, IntakeForm
from app.models.user import User
from app.schemas.intake import (
    HistoryFactDto, HistoryFactIn, IntakeFormDetailDto, IntakeFormDto, IntakeItemDto, IntakeItemIn,
)
from app.services import intake as svc

router = APIRouter()

_TYPES = {"application/pdf", "image/png", "image/jpeg"}


def _enqueue(form: IntakeForm) -> None:
    from app.workers.pipeline import intake_form_stage
    intake_form_stage.delay(str(form.id))


async def _form(form_id: uuid.UUID, user: User, db: AsyncSession, level=AccessLevel.view) -> IntakeForm:
    form = (await db.execute(select(IntakeForm).where(
        IntakeForm.id == form_id, IntakeForm.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(form.patient_id, user, db, level)
    return form


async def _detail(form: IntakeForm, db: AsyncSession, sheet: list[dict] | None = None) -> IntakeFormDetailDto:
    if sheet is None:
        sheet = svc.load_sheet(form, await get_patient_kek(db, form.patient_id))
    dto = IntakeFormDetailDto.model_validate(form)
    dto.items = [IntakeItemDto.model_validate(i) for i in sheet]
    return dto


@router.get("/patients/{patient_id}/intake-forms", response_model=list[IntakeFormDto])
async def list_intake_forms(patient_id: uuid.UUID, user: User = Depends(get_current_user),
                            db: AsyncSession = Depends(get_db)):
    await require_patient_access(patient_id, user, db)
    return (await db.execute(select(IntakeForm).where(
        IntakeForm.patient_id == patient_id, IntakeForm.is_deleted == False)  # noqa: E712
        .order_by(IntakeForm.created_at.desc()))).scalars().all()


@router.post("/patients/{patient_id}/intake-forms", response_model=IntakeFormDto, status_code=status.HTTP_201_CREATED)
async def upload_intake_form(
    patient_id: uuid.UUID,
    file: UploadFile = File(...),
    title: str | None = Form(None, max_length=256),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Its own entry point: an ordinary upload never becomes an Intake Form, and this
    one never becomes a Document."""
    from app.core.config import settings
    # the bundled sample is a letter, not a form; a demo takes no foreign files (test_demo_lock)
    if settings.demo_locked_upload_sha256:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="This is a public demo, intake form upload is disabled.")
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    if file.content_type not in _TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="PDF, PNG or JPEG only")
    data = await file.read()
    kek = await ensure_patient_kek(db, patient_id)
    ciphertext, wrapped_dek = encrypt_document(data, kek)
    form = IntakeForm(id=uuid.uuid4(), patient_id=patient_id, owner_id=user.id, title=(title or "").strip() or None,
                      file_name=file.filename, content_type=file.content_type, size=len(data),
                      encrypted_dek=wrapped_dek, status="reading")
    form.storage_path = f"{patient_id}/intake-{form.id}.enc"
    get_storage().write(form.storage_path, ciphertext)
    db.add(form)
    await db.commit()
    await db.refresh(form)
    try:
        _enqueue(form)
    except Exception as e:
        form.status, form.processing_error = "failed", f"Could not start reading: {e}"
        await db.commit()
    return form


@router.get("/intake-forms/{form_id}", response_model=IntakeFormDetailDto)
async def get_intake_form(form_id: uuid.UUID, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    return await _detail(await _form(form_id, user, db), db)


@router.get("/intake-forms/{form_id}/file")
async def get_intake_form_file(form_id: uuid.UUID, user: User = Depends(get_current_user),
                               db: AsyncSession = Depends(get_db)):
    form = await _form(form_id, user, db)
    data = decrypt_document(get_storage().read(form.storage_path), form.encrypted_dek,
                            await get_patient_kek(db, form.patient_id))
    return Response(content=data, media_type=form.content_type or "application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{form.file_name or "form"}"'})


@router.put("/intake-forms/{form_id}/items/{index}", response_model=IntakeFormDetailDto)
async def answer_item(form_id: uuid.UUID, index: int, body: IntakeItemIn,
                      user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    form = await _form(form_id, user, db, AccessLevel.contribute)
    if form.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a draft can be answered")
    kek = await get_patient_kek(db, form.patient_id)
    sheet = svc.load_sheet(form, kek)
    if not 0 <= index < len(sheet):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await svc.update_item(form, sheet[index], answer=body.answer, answer_given="answer" in body.model_fields_set,
                          aging=body.aging, confirm=body.confirm, owner_id=user.id, db=db)
    form.sheet = encrypt_str(json.dumps(sheet), kek)
    await db.commit()
    await db.refresh(form)
    return await _detail(form, db, sheet)


@router.post("/intake-forms/{form_id}/release", response_model=IntakeFormDetailDto)
async def release_intake_form(form_id: uuid.UUID, user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    form = await _form(form_id, user, db, AccessLevel.contribute)
    if form.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a draft can be released")
    kek = await get_patient_kek(db, form.patient_id)
    sheet = svc.load_sheet(form, kek)
    svc.release(form, sheet)
    form.sheet = encrypt_str(json.dumps(sheet), kek)
    await db.commit()
    await db.refresh(form)
    return await _detail(form, db, sheet)


@router.post("/intake-forms/{form_id}/revise", response_model=IntakeFormDto, status_code=status.HTTP_201_CREATED)
async def revise_intake_form(form_id: uuid.UUID, user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_db)):
    """A correction after release is a new sheet; the released one stays as handed in."""
    old = await _form(form_id, user, db, AccessLevel.contribute)
    if old.status != "released":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a released sheet is revised")
    form = IntakeForm(id=uuid.uuid4(), patient_id=old.patient_id, owner_id=user.id, title=old.title,
                      file_name=old.file_name, content_type=old.content_type, size=old.size,
                      encrypted_dek=old.encrypted_dek, sheet=old.sheet, status="draft")
    form.storage_path = f"{old.patient_id}/intake-{form.id}.enc"
    # same DEK, so the ciphertext copies as it is
    get_storage().write(form.storage_path, get_storage().read(old.storage_path))
    db.add(form)
    await db.commit()
    await db.refresh(form)
    return form


@router.post("/intake-forms/{form_id}/retry", response_model=IntakeFormDto)
async def retry_intake_form(form_id: uuid.UUID, user: User = Depends(get_current_user),
                            db: AsyncSession = Depends(get_db)):
    form = await _form(form_id, user, db, AccessLevel.contribute)
    if form.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a failed form is read again")
    form.status, form.processing_error = "reading", None
    await db.commit()
    await db.refresh(form)
    _enqueue(form)
    return form


@router.delete("/intake-forms/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_intake_form(form_id: uuid.UUID, user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_db)):
    """The original goes with it, and so do its visit-only History Facts (ADR 047)."""
    form = await _form(form_id, user, db, AccessLevel.contribute)
    await db.execute(delete(HistoryFact).where(HistoryFact.intake_form_id == form.id,
                                               HistoryFact.aging == "visit_only"))
    await db.execute(delete(IntakeForm).where(IntakeForm.id == form.id))
    get_storage().delete(form.storage_path)
    await db.commit()


@router.get("/patients/{patient_id}/history-facts", response_model=list[HistoryFactDto])
async def list_history_facts(patient_id: uuid.UUID, user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_db)):
    await require_patient_access(patient_id, user, db)
    return (await db.execute(select(HistoryFact).where(
        HistoryFact.patient_id == patient_id, HistoryFact.is_deleted == False)  # noqa: E712
        .order_by(HistoryFact.confirmed_on.desc(), HistoryFact.created_at.desc()))).scalars().all()


async def _history_fact(fact_id: uuid.UUID, user: User, db: AsyncSession) -> HistoryFact:
    fact = (await db.execute(select(HistoryFact).where(
        HistoryFact.id == fact_id, HistoryFact.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(fact.patient_id, user, db, AccessLevel.contribute)
    return fact


# no POST: a History Fact only comes into being through a form's question (GLOSSARY)
@router.put("/history-facts/{fact_id}", response_model=HistoryFactDto)
async def update_history_fact(fact_id: uuid.UUID, body: HistoryFactIn, user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    fact = await _history_fact(fact_id, user, db)
    fact.answer, fact.aging, fact.confirmed_on = body.answer, body.aging, date.today().isoformat()
    await db.commit()
    await db.refresh(fact)
    return fact


@router.delete("/history-facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_fact(fact_id: uuid.UUID, user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    fact = await _history_fact(fact_id, user, db)
    fact.is_deleted = True
    await db.commit()
