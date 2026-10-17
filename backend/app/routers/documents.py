import hashlib
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.core.encryption import decrypt_document, decrypt_str, encrypt_document
from app.core.patient_keys import ensure_patient_kek, get_patient_kek
from app.core.storage import get_storage
from app.deps import get_current_user
from app.models.correspondent import Correspondent
from app.models.document import DocumentReference
from app.models.favorite import DocumentFavorite
from app.models.user import User
from app.schemas.document import DocumentDetailDto, DocumentDto, UpdateDocumentRequest, VerifyDocumentRequest

router = APIRouter()


def _norm_condition(name: str) -> str:
    """Same normalisation as lab parameter names: case, whitespace, trailing colon."""
    return " ".join((name or "").strip().lower().rstrip(":.").split())


async def _favorite_doc_ids(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await db.execute(
        select(DocumentFavorite.document_id).where(
            DocumentFavorite.user_id == user_id,
            DocumentFavorite.is_deleted == False,  # noqa: E712
        )
    )
    return set(rows.scalars().all())


async def _reveal(doc: DocumentReference, db: AsyncSession) -> DocumentReference:
    """Decrypt a document's free-text fields in place before serialization (ADR-031).

    Last step before return — no autoflush follows, so the plaintext is never
    written back. Legacy plaintext / dicts (pre-migration) pass through."""
    import json
    kek = await get_patient_kek(db, doc.patient_id)
    doc.extracted_text = decrypt_str(doc.extracted_text, kek)
    ej = doc.extraction_json
    if isinstance(ej, str):
        dec = decrypt_str(ej, kek)
        doc.extraction_json = json.loads(dec) if dec else None
    return doc


@router.get("/patients/{patient_id}/documents", response_model=list[DocumentDto])
async def list_documents(
    patient_id: uuid.UUID,
    doc_type: str | None = Query(None, alias="type"),
    doc_status: str | None = Query(None, alias="status"),
    search: str | None = Query(None, alias="q", max_length=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = select(DocumentReference).where(DocumentReference.patient_id == patient_id, DocumentReference.is_deleted == False)  # noqa: E712
    if doc_type:
        q = q.where(DocumentReference.type == doc_type)
    if doc_status:
        q = q.where(DocumentReference.processing_status == doc_status)
    if search:
        # ponytail: ILIKE substring match, no ranking; pg_trgm/tsvector if it gets slow
        like = f"%{search}%"
        # extracted_text is ciphertext at rest (ADR-031) — body-text search is
        # embeddings-only (semantic) now; this matches metadata fields only.
        q = q.outerjoin(Correspondent, DocumentReference.correspondent_id == Correspondent.id).where(
            or_(
                DocumentReference.file_name.ilike(like),
                DocumentReference.description.ilike(like),
                DocumentReference.type.ilike(like),
                Correspondent.name.ilike(like),
            )
        )
    result = await db.execute(q.order_by(DocumentReference.created_at.desc()))
    docs = result.scalars().all()

    # Attach what each document says (summary, counts, out-of-range values) so the
    # list is readable without opening every file. One KEK for the whole patient.
    import json
    from app.core.doc_insights import build_insights
    from app.schemas.document import DocumentInsightsDto
    try:
        kek = await get_patient_kek(db, patient_id)
    except KeyError:
        kek = None
    favs = await _favorite_doc_ids(db, user.id)
    dtos = []
    for doc in docs:
        dto = DocumentDto.model_validate(doc)
        dto.is_favorite = doc.id in favs
        if kek and doc.extraction_json:
            try:
                ej = doc.extraction_json
                entities = json.loads(decrypt_str(ej, kek)) if isinstance(ej, str) else ej
                insights = build_insights(entities)
                if insights:
                    dto.insights = DocumentInsightsDto.model_validate(insights)
            except Exception:
                pass  # a single unreadable extraction must not blank the whole list
        dtos.append(dto)
    return dtos


@router.post("/patients/{patient_id}/documents/upload", response_model=DocumentDto, status_code=status.HTTP_201_CREATED)
async def upload_document(
    patient_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    description: str | None = Form(None),
    doc_type: str | None = Form(None, alias="type"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    from app.core.config import settings
    if settings.demo_locked_upload_sha256:
        from app.core.ratelimit import client_ip, enforce
        await enforce(f"rl:demo:upload:{client_ip(request)}", limit=5, window_seconds=3600)
    data = await file.read()
    file_hash = hashlib.sha256(data).hexdigest()

    from app.core.config import settings
    if settings.demo_locked_upload_sha256 and file_hash != settings.demo_locked_upload_sha256:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="This is a public demo — uploads are limited to the provided sample document.")

    # Block re-uploading the same file for this patient. A soft-deleted prior
    # upload doesn't count, so deleting then re-uploading still works.
    dup = await db.execute(select(DocumentReference).where(
        DocumentReference.patient_id == patient_id,
        DocumentReference.hash == file_hash,
        DocumentReference.is_deleted == False,  # noqa: E712
    ))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This file has already been uploaded for this patient.")

    kek = await ensure_patient_kek(db, patient_id)
    ciphertext, wrapped_dek = encrypt_document(data, kek)

    doc_id = uuid.uuid4()
    storage_key = f"{patient_id}/{doc_id}.enc"
    get_storage().write(storage_key, ciphertext)

    doc = DocumentReference(
        id=doc_id,
        patient_id=patient_id,
        owner_id=user.id,
        description=description,
        type=doc_type,
        file_name=file.filename,
        content_type=file.content_type,
        size=len(data),
        storage_path=storage_key,
        hash=file_hash,
        encrypted_dek=wrapped_dek,
        processing_status="pending",
        verification_status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Enqueue pipeline
    try:
        from app.workers.pipeline import ocr_stage
        ocr_stage.delay(str(doc.id))
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Failed to enqueue OCR task for doc %s: %s", doc.id, e)
        doc.processing_status = "failed"
        doc.processing_error = f"Could not start processing: {e}"
        await db.commit()

    return doc


@router.get("/documents/{doc_id}/file")
async def get_document_file(doc_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentReference).where(DocumentReference.id == doc_id, DocumentReference.is_deleted == False))  # noqa: E712
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(doc.patient_id, user, db)
    data = get_storage().read(doc.storage_path)
    kek = await get_patient_kek(db, doc.patient_id)
    data = decrypt_document(data, doc.encrypted_dek, kek)
    from fastapi.responses import Response
    return Response(
        content=data,
        media_type=doc.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{doc.file_name}"'},
    )


@router.get("/documents/{doc_id}", response_model=DocumentDto)
async def get_document(doc_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentReference).where(DocumentReference.id == doc_id, DocumentReference.is_deleted == False))  # noqa: E712
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(doc.patient_id, user, db)
    return doc


@router.get("/documents/{doc_id}/detail", response_model=DocumentDetailDto)
async def get_document_detail(doc_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentReference).where(DocumentReference.id == doc_id, DocumentReference.is_deleted == False))  # noqa: E712
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(doc.patient_id, user, db)
    return await _reveal(doc, db)


@router.post("/documents/{doc_id}/verify", response_model=DocumentDetailDto)
async def verify_document(
    doc_id: uuid.UUID,
    body: VerifyDocumentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DocumentReference).where(DocumentReference.id == doc_id, DocumentReference.is_deleted == False))  # noqa: E712
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(doc.patient_id, user, db, AccessLevel.contribute)

    from app.models.calendar import CalendarEvent
    from app.models.condition import Condition
    from app.models.medication import MedicationStatement
    from app.models.observation import Observation
    from app.models.recommendation import Recommendation

    try:
        # Soft-delete existing extracted entities from this doc. Conditions are
        # handled below — they can cite several documents (#133), so "this doc no
        # longer names it" only kills a condition nothing else backs.
        for model in [Observation, MedicationStatement, CalendarEvent, Recommendation]:
            existing = await db.execute(select(model).where(model.document_reference_id == doc_id, model.is_deleted == False))  # noqa: E712
            for entity in existing.scalars().all():
                entity.is_deleted = True

        # Retract only *unconfirmed* pipeline expense proposals from this doc — a
        # confirmed Expense is the User's kept record and must survive re-verification.
        from app.models.expense import EXPENSE_CATEGORIES, Expense
        stale_exp = await db.execute(select(Expense).where(
            Expense.document_reference_id == doc_id,
            Expense.source == "pipeline", Expense.status == "proposed",
            Expense.is_deleted == False,  # noqa: E712
        ))
        for e in stale_exp.scalars().all():
            e.is_deleted = True

        # Retract this doc's citations; the re-add loop below re-attaches what the
        # (possibly corrected) payload still names. All mutations go through the
        # `sources` relationship — a row added past a loaded collection stays
        # invisible on it, and selectinload will not overwrite what is loaded.
        from sqlalchemy.orm import selectinload
        from app.models.condition import ConditionSource
        citing = (await db.execute(
            select(Condition).options(selectinload(Condition.sources)).where(
                Condition.id.in_(select(ConditionSource.condition_id).where(
                    ConditionSource.document_reference_id == doc_id)),
                Condition.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
        for cond in citing:
            # delete-orphan cascade turns the removal into DELETEs
            cond.sources = [s for s in cond.sources if s.document_reference_id != doc_id]
            if cond.sources:
                if cond.document_reference_id == doc_id:
                    cond.document_reference_id = sorted(cond.sources, key=lambda s: s.created_at)[0].document_reference_id
            elif cond.document_reference_id == doc_id:
                # extraction-born and nothing else ever named it
                cond.is_deleted = True
            # manual conditions (document_reference_id is null/other) just lose the citation
        # flush now: the re-add loop may insert the same (condition, doc) pair, and
        # the unit of work would otherwise INSERT before DELETE → unique violation
        await db.flush()

        # Create new entities
        from app.services.lab_codes import canonical_code, parse_number, parse_reference_range, resolve_panel

        doc_date = doc.issued_date.isoformat() if doc.issued_date else None
        for obs_data in body.observations:
            raw_val = obs_data.get("value")
            # "13,9" off a German report is a number, not text. Storing it as text
            # drops the point out of the trend chart while the list still shows it.
            value_quantity = parse_number(raw_val)
            value_string = None if value_quantity is not None or raw_val is None else str(raw_val)
            display = obs_data.get("type")
            code = canonical_code(display)
            ref_raw = obs_data.get("reference_range")
            ref_low, ref_high = parse_reference_range(ref_raw)
            # Canonical panel from the analyte (stable), else the normalised heading (ADR 029).
            panel = resolve_panel(code, obs_data.get("panel"))
            # A value from a lab panel is a lab result; a standalone vital is a measurement.
            category = obs_data.get("category") or ("lab" if panel else "measurement")
            db.add(Observation(
                patient_id=doc.patient_id,
                owner_id=user.id,
                document_reference_id=doc_id,
                code=code,
                code_display=display,
                category=category,
                panel=panel,
                effective_date_time=obs_data.get("date") or doc_date,
                value_quantity=value_quantity,
                value_string=value_string,
                value_unit=obs_data.get("unit"),
                reference_range=ref_raw,
                ref_low=ref_low,
                ref_high=ref_high,
            ))

        # Every verified document used to re-add its diagnoses, so eight letters
        # naming "Globale Entwicklungsverzögerung" produced eight rows — a pile of
        # paper, not a history (#129). A re-mention now ATTACHES as a further
        # source instead of being discarded (#133). Only EXACT matches after
        # normalising case and whitespace: deciding that "Ataxie" and "Leichte
        # Ataxie" are the same condition is a medical judgement, not a string
        # operation (#113).
        existing_conds = (await db.execute(
            select(Condition).options(selectinload(Condition.sources)).where(
                Condition.patient_id == doc.patient_id,
                Condition.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
        by_key = {_norm_condition(c.code_display): c for c in existing_conds}

        for dx_data in body.diagnoses:
            name = dx_data.get("name") or dx_data.get("code_display") or ""
            if not name:
                continue
            key = _norm_condition(name)
            provisional = dx_data.get("verification_status") == "provisional"
            reaction = (dx_data.get("reaction") or None) if dx_data.get("category") == "allergy" else None  # #193
            if key in by_key:
                cond = by_key[key]
                if reaction and not cond.note:
                    cond.note = reaction
                if not any(s.document_reference_id == doc_id for s in cond.sources):
                    cond.sources.append(ConditionSource(document_reference_id=doc_id))
                # A letter that states it confirms a suspicion; one that only
                # suspects it never downgrades a confirmed Diagnosis (#271).
                if cond.verification_status == "provisional" and not provisional:
                    cond.verification_status = None
                continue
            cond = Condition(
                patient_id=doc.patient_id,
                owner_id=user.id,
                document_reference_id=doc_id,
                code_display=name,
                clinical_status=dx_data.get("status") or "active",
                category=dx_data.get("category"),  # "allergy" or null (#191)
                severity=dx_data.get("severity"),
                note=reaction,
                onset_date_time=dx_data.get("onset_date"),
                verification_status="provisional" if provisional else None,
            )
            cond.sources.append(ConditionSource(document_reference_id=doc_id))
            db.add(cond)
            by_key[key] = cond

        # A medication is a COURSE, not a state: "Valproat 300mg" in the 2024 letter
        # and "Valproat 500mg" in the 2026 one are a dose change, not a duplicate —
        # merging them would delete history. So only skip a re-mention that carries
        # no new information: same drug, same dosage, still running (#129). A changed
        # dose creates a new row; ending the old one is the caregiver's call, not
        # ours (that would be inferring "she switched").
        running = (await db.execute(
            select(MedicationStatement).where(
                MedicationStatement.patient_id == doc.patient_id,
                MedicationStatement.status == "active",
                MedicationStatement.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
        seen_meds = {
            (_norm_condition(m.medication_display), _norm_condition(m.dosage_text or ""))
            for m in running
        }

        for med_data in body.medications:
            med_name = med_data.get("name") or med_data.get("display") or ""
            if not med_name:
                continue
            med_key = (_norm_condition(med_name), _norm_condition(med_data.get("dosage") or ""))
            if med_key in seen_meds:
                continue
            seen_meds.add(med_key)
            db.add(MedicationStatement(
                patient_id=doc.patient_id,
                owner_id=user.id,
                document_reference_id=doc_id,
                medication_display=med_name,
                dosage_text=med_data.get("dosage"),
                # The letter of 19.03. tells us what she was taking THEN. We used to
                # throw that away and leave the start empty (#128); the document's own
                # date is the honest answer unless the document names one itself.
                effective_start=med_data.get("start_date") or doc_date,
                effective_end=med_data.get("end_date"),
                date_asserted=doc_date,
            ))

        for appt in body.appointments:
            date = appt.get("date")
            if not date:
                continue
            time = appt.get("time")
            start_at = f"{date}T{time}:00" if time else date
            all_day = not bool(time)
            purpose = appt.get("purpose")
            provider = appt.get("provider")
            if purpose:
                title = purpose
            elif provider:
                title = f"Appointment with {provider}"
            else:
                title = "Appointment"
            db.add(CalendarEvent(
                patient_id=doc.patient_id,
                owner_id=user.id,
                document_reference_id=doc_id,
                title=title,
                start_at=start_at,
                all_day=all_day,
                provider=provider,
                location=appt.get("location"),
                purpose=purpose,
                source="pipeline",
            ))

        # A Kassenbescheid with a Rechtsbehelfsbelehrung yields a Widerspruch deadline
        # (ADR 041). One gate, like an appointment: an unconfirmed deadline that the
        # system knows but never reminds about is the exact harm this prevents. The
        # date is computed here, never by the model, and the payload may carry a
        # deadline_date the User corrected on the verification screen.
        if body.decision:
            from app.services.deadlines import parse_iso_date, widerspruch_deadline
            dec = body.decision
            months = dec.get("deadline_months")
            months = months if isinstance(months, int) and 1 <= months <= 12 else 1
            decided_on = parse_iso_date(dec.get("decision_date"))
            deadline = parse_iso_date(dec.get("deadline_date")) or (
                widerspruch_deadline(decided_on, months) if decided_on else None
            )
            subject = (dec.get("subject") or "").strip()
            authority = (dec.get("authority") or "").strip() or None
            if deadline:
                lines = []
                if dec.get("file_reference"):
                    lines.append(f"Aktenzeichen: {dec['file_reference']}")
                if dec.get("grounds"):
                    lines.append(f"Begründung der Kasse: {dec['grounds']}")
                if decided_on:
                    lines.append(
                        f"Berechnet aus dem Bescheid vom {decided_on.isoformat()} "
                        f"(+3 Tage Bekanntgabe, +{months} Monat(e)). Ohne Gewähr — "
                        "das tatsächliche Fristende kann abweichen. Im Zweifel früher "
                        "widersprechen oder beraten lassen."
                    )
                db.add(CalendarEvent(
                    patient_id=doc.patient_id,
                    owner_id=user.id,
                    document_reference_id=doc_id,
                    title=f"Widerspruchsfrist: {subject}" if subject else "Widerspruchsfrist",
                    description="\n".join(lines) or None,
                    category="deadline",
                    start_at=deadline.isoformat(),
                    all_day=True,
                    provider=authority,
                    source="pipeline",
                ))

            # The same Bescheid also GRANTS a Pflegegrad, and that is a record with a
            # history, not a field (ADR 042). The module table is only kept if the
            # arithmetic agrees with it: a Bescheid prints both Einzelpunkte and
            # gewichtete Punkte, and reading the wrong column is the likely failure.
            from app.services.pflegegrad import MODULE_KEYS, modules_within_limits, points_match_grade
            grade = dec.get("pflegegrad")
            grade = grade if isinstance(grade, int) and 1 <= grade <= 5 else None
            total = dec.get("total_points")
            total = float(total) if isinstance(total, (int, float)) and 0 <= total <= 100 else None
            valid_from = parse_iso_date(dec.get("valid_from")) or decided_on
            valid_until = parse_iso_date(dec.get("valid_until"))

            raw_modules = dec.get("modules")
            modules = {}
            if isinstance(raw_modules, dict):
                modules = {k: float(v) for k, v in raw_modules.items()
                           if k in MODULE_KEYS and isinstance(v, (int, float))}
            if not (points_match_grade(total, grade) and modules_within_limits(modules)):
                modules = {}  # keep the grade and the date, drop numbers that do not add up

            if grade or total or modules:
                from app.models.einstufung import Einstufung
                db.add(Einstufung(
                    patient_id=doc.patient_id,
                    owner_id=user.id,
                    document_reference_id=doc_id,
                    pflegegrad=grade,
                    total_points=total,
                    valid_from=valid_from.isoformat() if valid_from else None,
                    valid_until=valid_until.isoformat() if valid_until else None,
                    authority=authority,
                    file_reference=(dec.get("file_reference") or None),
                    source="pipeline",
                    **{f"module_{k}": v for k, v in modules.items()},
                ))

            # A befristete Einstufung is a date with a consequence: benefits stop and
            # the follow-up application wants months, not days, of notice (ADR 042).
            if valid_until:
                db.add(CalendarEvent(
                    patient_id=doc.patient_id,
                    owner_id=user.id,
                    document_reference_id=doc_id,
                    title=f"Pflegegrad {grade} läuft aus" if grade else "Einstufung läuft aus",
                    description=(
                        "Die Einstufung ist bis zu diesem Tag befristet. Ein Folgeantrag "
                        "braucht eine neue Begutachtung und damit Vorlauf."
                    ),
                    category="deadline",
                    start_at=valid_until.isoformat(),
                    all_day=True,
                    provider=authority,
                    purpose="einstufung_expiry",  # picked up by the reminder lead times
                    source="pipeline",
                ))

        for rec_text in body.recommendations:
            if rec_text and rec_text.strip():
                db.add(Recommendation(patient_id=doc.patient_id, owner_id=user.id, document_reference_id=doc_id, text=rec_text.strip()))

        # Extracted invoice amounts enter as PROPOSED — a wrong OCR sum must never
        # land in a tax/insurance total unconfirmed (#218). The User confirms them
        # in the Expenses overview; only then do they count.
        from decimal import Decimal, InvalidOperation
        for exp in body.expenses:
            raw_amt = exp.get("amount")
            if raw_amt in (None, ""):
                continue
            try:
                amount = Decimal(str(raw_amt))
            except (InvalidOperation, ValueError):
                continue
            cat = exp.get("category")
            db.add(Expense(
                patient_id=doc.patient_id,
                owner_id=user.id,
                document_reference_id=doc_id,
                amount=amount,
                incurred_on=exp.get("date") or doc_date,
                category=cat if cat in EXPENSE_CATEGORIES else "other",
                note=exp.get("note"),
                correspondent_id=doc.correspondent_id,
                status="proposed",
                source="pipeline",
            ))

        doc.verification_status = "verified"
        await db.commit()
        await db.refresh(doc)
    except Exception:
        import traceback, sys
        traceback.print_exc(file=sys.stdout)
        raise
    return await _reveal(doc, db)


@router.patch("/documents/{doc_id}", response_model=DocumentDto)
async def update_document(
    doc_id: uuid.UUID,
    body: UpdateDocumentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DocumentReference).where(DocumentReference.id == doc_id, DocumentReference.is_deleted == False))  # noqa: E712
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(doc.patient_id, user, db, AccessLevel.contribute)
    if body.issued_date is not None:
        doc.issued_date = body.issued_date
    if body.description is not None:
        doc.description = body.description
    if body.type is not None:
        doc.type = body.type
    if "correspondent_id" in body.model_fields_set:
        doc.correspondent_id = body.correspondent_id
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentReference).where(DocumentReference.id == doc_id, DocumentReference.is_deleted == False))  # noqa: E712
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(doc.patient_id, user, db, AccessLevel.contribute)
    from app.core.config import settings
    if settings.demo_locked_upload_sha256 and doc.hash != settings.demo_locked_upload_sha256:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is a public demo, it is read-only.")

    # Cascade: remove everything this document extracted, so deleting a document
    # (e.g. an accidental duplicate) also clears its observations/diagnoses/etc.
    from app.models.calendar import CalendarEvent
    from app.models.condition import Condition
    from app.models.medication import MedicationStatement
    from app.models.observation import Observation
    from app.models.recommendation import Recommendation

    for model in [Observation, Condition, MedicationStatement, CalendarEvent, Recommendation]:
        rows = await db.execute(select(model).where(model.document_reference_id == doc_id, model.is_deleted == False))  # noqa: E712
        for entity in rows.scalars().all():
            entity.is_deleted = True

    doc.is_deleted = True
    await db.commit()


@router.put("/documents/{doc_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def add_document_favorite(doc_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = (await db.execute(select(DocumentReference).where(
        DocumentReference.id == doc_id, DocumentReference.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(doc.patient_id, user, db)
    existing = await db.execute(select(DocumentFavorite).where(
        DocumentFavorite.user_id == user.id, DocumentFavorite.document_id == doc_id,
        DocumentFavorite.is_deleted == False,  # noqa: E712
    ))
    if existing.scalar_one_or_none() is None:
        db.add(DocumentFavorite(user_id=user.id, document_id=doc_id))
        await db.commit()


@router.delete("/documents/{doc_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document_favorite(doc_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentFavorite).where(
        DocumentFavorite.user_id == user.id, DocumentFavorite.document_id == doc_id,
    ))
    for fav in result.scalars().all():
        await db.delete(fav)
    await db.commit()


@router.post("/documents/{doc_id}/retry")
async def retry_document(doc_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentReference).where(DocumentReference.id == doc_id, DocumentReference.is_deleted == False))  # noqa: E712
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(doc.patient_id, user, db, AccessLevel.contribute)
    doc.processing_status = "pending"
    doc.processing_error = None
    await db.commit()
    try:
        from app.workers.pipeline import ocr_stage
        task = ocr_stage.delay(str(doc.id))
        return {"job_id": task.id, "stage": "ocr"}
    except Exception:
        return {"job_id": None, "stage": "ocr"}
