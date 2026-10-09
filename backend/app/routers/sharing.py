"""Consent-gated file sharing — see docs/adr/020-consent-gated-file-sharing.md.

Two sides:
- Purpose Managers (Coordinator/admin) create Sharing Purposes and collect shared files.
- Caregivers (any User with patient access) respond to the org-wide ask on the patient page.
"""

import hashlib
import io
import uuid
import zipfile
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import require_patient_access
from app.core.database import get_db
from app.core.encryption import decrypt_document
from app.core.storage import get_storage
from app.deps import get_current_user, require_manager
from app.models.access import PatientAccess
from app.models.audit import AuditLog
from app.models.document import DocumentReference
from app.models.patient import Patient
from app.models.sharing import (
    IdentificationMode,
    Share,
    ShareDecline,
    SharingPurpose,
    SharingPurposeStatus,
    ShareStatus,
)
from app.models.user import User
from app.schemas.sharing import (
    CollectedShareDto,
    ConsentRequest,
    OpenRequestDto,
    ShareDto,
    SharingPurposeCreateRequest,
    SharingPurposeDto,
    SharingPurposeUpdateRequest,
)

router = APIRouter()


# --- helpers -----------------------------------------------------------------

def _audit(db: AsyncSession, user: User, action: str, entity_type: str, entity_id, changes: dict | None = None) -> None:
    name = " ".join(filter(None, [user.first_name, user.last_name])) or user.email
    db.add(AuditLog(
        timestamp=datetime.now(UTC),
        user_id=user.id,
        user_name=name,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        changes=changes,
    ))


def _pseudonym(purpose_id: uuid.UUID, patient_id: uuid.UUID) -> str:
    h = hashlib.sha256(f"{purpose_id}:{patient_id}".encode()).hexdigest()
    return f"Patient #{h[:6].upper()}"


def _is_open(purpose: SharingPurpose, now: datetime) -> bool:
    if purpose.status != SharingPurposeStatus.open:
        return False
    return purpose.expires_at is None or purpose.expires_at > now


async def _share_count(db: AsyncSession, purpose_id: uuid.UUID) -> int:
    return await db.scalar(
        select(func.count()).select_from(Share).where(
            Share.sharing_purpose_id == purpose_id, Share.status == ShareStatus.active
        )
    ) or 0


async def _has_any_share(db: AsyncSession, purpose_id: uuid.UUID) -> bool:
    row = await db.execute(select(Share.id).where(Share.sharing_purpose_id == purpose_id).limit(1))
    return row.first() is not None


async def _purpose_dto(db: AsyncSession, purpose: SharingPurpose) -> SharingPurposeDto:
    dto = SharingPurposeDto.model_validate(purpose)
    dto.share_count = await _share_count(db, purpose.id)
    return dto


async def _get_purpose(purpose_id: uuid.UUID, db: AsyncSession) -> SharingPurpose:
    result = await db.execute(
        select(SharingPurpose).where(SharingPurpose.id == purpose_id, SharingPurpose.is_deleted == False)  # noqa: E712
    )
    purpose = result.scalar_one_or_none()
    if not purpose:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return purpose


# --- Purpose Manager side (Coordinator/admin) --------------------------------

@router.post("/sharing-purposes", response_model=SharingPurposeDto, status_code=status.HTTP_201_CREATED)
async def create_purpose(
    body: SharingPurposeCreateRequest,
    user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    purpose = SharingPurpose(
        name=body.name,
        description=body.description,
        identification_mode=body.identification_mode,
        status=SharingPurposeStatus.open,
        expires_at=body.expires_at,
        created_by_user_id=user.id,
    )
    db.add(purpose)
    await db.flush()
    _audit(db, user, "created", "SharingPurpose", purpose.id)
    await db.commit()
    await db.refresh(purpose)
    return await _purpose_dto(db, purpose)


@router.get("/sharing-purposes", response_model=list[SharingPurposeDto])
async def list_purposes(
    user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SharingPurpose)
        .where(SharingPurpose.is_deleted == False)  # noqa: E712
        .order_by(SharingPurpose.created_at.desc())
    )
    return [await _purpose_dto(db, p) for p in result.scalars().all()]


@router.get("/sharing-purposes/{purpose_id}", response_model=SharingPurposeDto)
async def get_purpose(
    purpose_id: uuid.UUID,
    user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    purpose = await _get_purpose(purpose_id, db)
    return await _purpose_dto(db, purpose)


@router.patch("/sharing-purposes/{purpose_id}", response_model=SharingPurposeDto)
async def update_purpose(
    purpose_id: uuid.UUID,
    body: SharingPurposeUpdateRequest,
    user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    purpose = await _get_purpose(purpose_id, db)
    locked = await _has_any_share(db, purpose.id)

    if body.name is not None:
        purpose.name = body.name
    if body.expires_at is not None:
        purpose.expires_at = body.expires_at
    # Consent terms freeze once any Share exists, so the consent record cannot drift.
    if body.description is not None or body.identification_mode is not None:
        if locked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Consent terms are locked once a file has been shared. Create a new Sharing Purpose instead.",
            )
        if body.description is not None:
            purpose.description = body.description
        if body.identification_mode is not None:
            purpose.identification_mode = body.identification_mode

    _audit(db, user, "updated", "SharingPurpose", purpose.id)
    await db.commit()
    await db.refresh(purpose)
    return await _purpose_dto(db, purpose)


@router.post("/sharing-purposes/{purpose_id}/close", response_model=SharingPurposeDto)
async def close_purpose(
    purpose_id: uuid.UUID,
    user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    purpose = await _get_purpose(purpose_id, db)
    purpose.status = SharingPurposeStatus.closed
    purpose.closed_at = datetime.now(UTC)
    _audit(db, user, "updated", "SharingPurpose", purpose.id, {"status": {"new": "closed"}})
    await db.commit()
    await db.refresh(purpose)
    return await _purpose_dto(db, purpose)


async def _collect_active_shares(purpose: SharingPurpose, db: AsyncSession):
    """Return (Share, DocumentReference, Patient) for each active, still-existing share."""
    result = await db.execute(
        select(Share, DocumentReference, Patient)
        .join(DocumentReference, DocumentReference.id == Share.document_id)
        .join(Patient, Patient.id == Share.patient_id)
        .where(
            Share.sharing_purpose_id == purpose.id,
            Share.status == ShareStatus.active,
            DocumentReference.is_deleted == False,  # noqa: E712
            Patient.is_deleted == False,  # noqa: E712
        )
        .order_by(Share.consented_at.desc())
    )
    return result.all()


def _patient_label(purpose: SharingPurpose, patient: Patient) -> str:
    if purpose.identification_mode == IdentificationMode.anonymous:
        return _pseudonym(purpose.id, patient.id)
    return f"{patient.family_name}, {patient.given_name}"


@router.get("/sharing-purposes/{purpose_id}/shares", response_model=list[CollectedShareDto])
async def list_collected_shares(
    purpose_id: uuid.UUID,
    user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    purpose = await _get_purpose(purpose_id, db)
    anonymous = purpose.identification_mode == IdentificationMode.anonymous
    out = []
    for share, doc, patient in await _collect_active_shares(purpose, db):
        out.append(CollectedShareDto(
            share_id=share.id,
            document_id=doc.id,
            file_name=doc.file_name,
            content_type=doc.content_type,
            size=doc.size,
            consented_at=share.consented_at,
            patient_label=_patient_label(purpose, patient),
            patient_id=None if anonymous else patient.id,
        ))
    return out


async def _read_decrypted(doc: DocumentReference, db: AsyncSession) -> bytes:
    from app.core.patient_keys import get_patient_kek
    kek = await get_patient_kek(db, doc.patient_id)
    data = get_storage().read(doc.storage_path)
    return decrypt_document(data, doc.encrypted_dek, kek)


@router.get("/shares/{share_id}/file")
async def download_share_file(
    share_id: uuid.UUID,
    user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Share, DocumentReference).join(DocumentReference, DocumentReference.id == Share.document_id).where(
            Share.id == share_id,
            Share.status == ShareStatus.active,
            DocumentReference.is_deleted == False,  # noqa: E712
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    share, doc = row
    data = await _read_decrypted(doc, db)
    return Response(
        content=data,
        media_type=doc.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{doc.file_name or doc.id}"'},
    )


@router.get("/sharing-purposes/{purpose_id}/download")
async def download_purpose_bundle(
    purpose_id: uuid.UUID,
    user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    purpose = await _get_purpose(purpose_id, db)
    rows = await _collect_active_shares(purpose, db)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No shared files to download.")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for share, doc, patient in rows:
            label = _patient_label(purpose, patient).replace("/", "-").replace(", ", "_")
            # share id prefix keeps paths unique without bookkeeping
            zf.writestr(f"{label}/{share.id}_{doc.file_name or doc.id}", await _read_decrypted(doc, db))

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in purpose.name) or "shares"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


# --- Caregiver / Patient side -----------------------------------------------

@router.get("/patients/{patient_id}/sharing/open-requests", response_model=list[OpenRequestDto])
async def list_open_requests(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    now = datetime.now(UTC)
    shared = select(Share.sharing_purpose_id).where(
        Share.patient_id == patient_id, Share.status == ShareStatus.active
    )
    declined = select(ShareDecline.sharing_purpose_id).where(ShareDecline.patient_id == patient_id)
    result = await db.execute(
        select(SharingPurpose).where(
            SharingPurpose.is_deleted == False,  # noqa: E712
            SharingPurpose.status == SharingPurposeStatus.open,
            or_(SharingPurpose.expires_at == None, SharingPurpose.expires_at > now),  # noqa: E711
            SharingPurpose.id.notin_(shared),
            SharingPurpose.id.notin_(declined),
        ).order_by(SharingPurpose.created_at.desc())
    )
    return result.scalars().all()


@router.get("/patients/{patient_id}/sharing/shares", response_model=list[ShareDto])
async def list_patient_shares(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(
        select(Share, SharingPurpose, DocumentReference)
        .join(SharingPurpose, SharingPurpose.id == Share.sharing_purpose_id)
        .join(DocumentReference, DocumentReference.id == Share.document_id)
        .where(Share.patient_id == patient_id)
        .order_by(Share.consented_at.desc())
    )
    out = []
    for share, purpose, doc in result.all():
        dto = ShareDto.model_validate(share)
        dto.purpose_name = purpose.name
        dto.document_file_name = doc.file_name
        out.append(dto)
    return out


async def _consenter_is_legal(patient_id: uuid.UUID, user: User, db: AsyncSession) -> bool:
    result = await db.execute(
        select(PatientAccess).where(
            PatientAccess.patient_id == patient_id,
            PatientAccess.user_id == user.id,
            PatientAccess.is_legal_representative == True,  # noqa: E712
            PatientAccess.revoked_at == None,  # noqa: E711
            PatientAccess.is_deleted == False,  # noqa: E712
        )
    )
    return result.first() is not None


@router.post("/patients/{patient_id}/sharing/purposes/{purpose_id}/consent", response_model=list[ShareDto])
async def consent(
    patient_id: uuid.UUID,
    purpose_id: uuid.UUID,
    body: ConsentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    purpose = await _get_purpose(purpose_id, db)
    if not _is_open(purpose, datetime.now(UTC)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sharing Purpose is no longer open.")
    if not body.document_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No documents selected.")

    is_legal = await _consenter_is_legal(patient_id, user, db)
    now = datetime.now(UTC)
    created: list[Share] = []
    for doc_id in body.document_ids:
        doc_res = await db.execute(
            select(DocumentReference).where(
                DocumentReference.id == doc_id,
                DocumentReference.patient_id == patient_id,
                DocumentReference.is_deleted == False,  # noqa: E712
            )
        )
        if not doc_res.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {doc_id} not found for this patient.")

        existing_res = await db.execute(
            select(Share).where(Share.sharing_purpose_id == purpose_id, Share.document_id == doc_id)
        )
        share = existing_res.scalar_one_or_none()
        if share:
            if share.status == ShareStatus.active:
                continue  # already shared
            share.status = ShareStatus.active  # re-consent a previously revoked share
            share.revoked_at = None
            share.consented_by_user_id = user.id
            share.consented_at = now
            share.consented_legal = is_legal
        else:
            share = Share(
                sharing_purpose_id=purpose_id,
                document_id=doc_id,
                patient_id=patient_id,
                status=ShareStatus.active,
                consented_by_user_id=user.id,
                consented_at=now,
                consented_legal=is_legal,
            )
            db.add(share)
            await db.flush()
        _audit(db, user, "created", "Share", share.id, {
            "purpose": str(purpose_id), "document": str(doc_id), "mode": purpose.identification_mode,
        })
        created.append(share)

    # Consenting clears any prior decline for this purpose.
    await db.execute(
        ShareDecline.__table__.delete().where(
            ShareDecline.sharing_purpose_id == purpose_id, ShareDecline.patient_id == patient_id
        )
    )
    await db.commit()

    out = []
    for share in created:
        await db.refresh(share)
        dto = ShareDto.model_validate(share)
        dto.purpose_name = purpose.name
        out.append(dto)
    return out


@router.post("/patients/{patient_id}/sharing/purposes/{purpose_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline(
    patient_id: uuid.UUID,
    purpose_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    await _get_purpose(purpose_id, db)
    existing = await db.execute(
        select(ShareDecline).where(
            ShareDecline.sharing_purpose_id == purpose_id, ShareDecline.patient_id == patient_id
        )
    )
    if existing.scalar_one_or_none():
        return
    marker = ShareDecline(
        sharing_purpose_id=purpose_id,
        patient_id=patient_id,
        declined_by_user_id=user.id,
        declined_at=datetime.now(UTC),
    )
    db.add(marker)
    await db.flush()
    _audit(db, user, "created", "ShareDecline", marker.id, {"purpose": str(purpose_id), "patient": str(patient_id)})
    await db.commit()


@router.post("/patients/{patient_id}/sharing/shares/{share_id}/revoke", response_model=ShareDto)
async def revoke_share(
    patient_id: uuid.UUID,
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(
        select(Share).where(Share.id == share_id, Share.patient_id == patient_id)
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if share.status == ShareStatus.active:
        share.status = ShareStatus.revoked
        share.revoked_at = datetime.now(UTC)
        _audit(db, user, "updated", "Share", share.id, {"status": {"new": "revoked"}})
        await db.commit()
        await db.refresh(share)
    return ShareDto.model_validate(share)
