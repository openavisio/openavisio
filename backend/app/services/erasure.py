"""GDPR Article 17 right-to-erasure service.

Patient erasure: cascade hard-delete of all clinical data + storage files + audit history.
User erasure: anonymise PII fields, hard-delete credentials and access grants, scrub audit names.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.storage import get_storage
from app.models.access import PatientAccess, PatientCaregiverInvite
from app.models.audit import AuditLog
from app.models.calendar import CalendarEvent, CalendarFeed
from app.models.chat import ChatMessage, DocumentChunk
from app.models.condition import Condition
from app.models.diary import DiaryEntry, DiaryTemplate
from app.models.document import DocumentReference
from app.models.group import GroupMembership
from app.models.einstufung import Einstufung
from app.models.emergency_plan import EmergencyPlan
from app.models.care_notes import CareNotes
from app.models.carer_update import CarerUpdate
from app.models.expense import Expense
from app.models.incident import Incident
from app.models.intake import HistoryFact, IntakeForm
from app.models.medication import MedicationStatement
from app.models.observation import Observation
from app.models.passkey import PasskeyCredential
from app.models.patient import Patient
from app.models.recommendation import Recommendation
from app.models.share_link import DocumentShareLink, DocumentShareLinkHandout, DocumentShareLinkItem
from app.models.sharing import Share, ShareDecline
from app.models.user import User


async def erase_patient(
    patient_id: uuid.UUID,
    actor: User,
    db: AsyncSession,
) -> None:
    """Cascade hard-delete a Patient and all their data.

    Storage files are deleted before the DB transaction commits; if storage
    deletion fails the DB transaction is rolled back and an exception is raised.
    """
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False)  # noqa: E712
    )
    patient = result.scalar_one_or_none()
    if not patient:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Collect storage paths and all entity IDs before deleting rows
    # (audit log entries reference individual row UUIDs, not patient_id)
    docs_result = await db.execute(
        select(DocumentReference.id, DocumentReference.storage_path).where(
            DocumentReference.patient_id == patient_id,
        )
    )
    doc_rows = docs_result.all()
    storage_paths = [r.storage_path for r in doc_rows if r.storage_path]
    # the uploaded Intake Form originals go with their forms (ADR 047)
    forms = (await db.execute(select(IntakeForm.id, IntakeForm.storage_path).where(
        IntakeForm.patient_id == patient_id))).all()
    storage_paths += [r.storage_path for r in forms]
    if patient.photo_storage_path:  # optional patient photo blob (ADR-031)
        storage_paths.append(patient.photo_storage_path)
    doc_ids = [str(r.id) for r in doc_rows]

    async def _collect(model, id_col):
        r = await db.execute(select(model.id).where(id_col == patient_id))
        return [str(row[0]) for row in r.all()]

    cond_ids    = await _collect(Condition, Condition.patient_id)
    med_ids     = await _collect(MedicationStatement, MedicationStatement.patient_id)
    obs_ids     = await _collect(Observation, Observation.patient_id)
    inc_ids     = await _collect(Incident, Incident.patient_id)
    exp_ids     = await _collect(Expense, Expense.patient_id)
    einst_ids   = await _collect(Einstufung, Einstufung.patient_id)
    carer_ids   = await _collect(CarerUpdate, CarerUpdate.patient_id)
    fact_ids    = await _collect(HistoryFact, HistoryFact.patient_id)
    form_ids    = [str(r.id) for r in forms]
    diary_ids   = await _collect(DiaryEntry, DiaryEntry.patient_id)
    cal_ids     = await _collect(CalendarEvent, CalendarEvent.patient_id)
    feed_ids    = await _collect(CalendarFeed, CalendarFeed.patient_id)
    rec_ids     = await _collect(Recommendation, Recommendation.patient_id)
    share_ids   = await _collect(Share, Share.patient_id)
    decline_ids = await _collect(ShareDecline, ShareDecline.patient_id)
    link_ids    = await _collect(DocumentShareLink, DocumentShareLink.patient_id)

    # Delete all clinical data rows (hard delete)
    await db.execute(delete(DocumentChunk).where(DocumentChunk.patient_id == patient_id))
    await db.execute(delete(ChatMessage).where(ChatMessage.patient_id == patient_id))
    await db.execute(delete(Recommendation).where(Recommendation.patient_id == patient_id))
    await db.execute(delete(Observation).where(Observation.patient_id == patient_id))
    await db.execute(delete(Condition).where(Condition.patient_id == patient_id))
    await db.execute(delete(MedicationStatement).where(MedicationStatement.patient_id == patient_id))
    await db.execute(delete(Incident).where(Incident.patient_id == patient_id))
    await db.execute(delete(Expense).where(Expense.patient_id == patient_id))
    # a decision about a named person's care need is theirs (ADR 042)
    await db.execute(delete(Einstufung).where(Einstufung.patient_id == patient_id))
    await db.execute(delete(EmergencyPlan).where(EmergencyPlan.patient_id == patient_id))
    await db.execute(delete(CareNotes).where(CareNotes.patient_id == patient_id))
    await db.execute(delete(CarerUpdate).where(CarerUpdate.patient_id == patient_id))
    await db.execute(delete(HistoryFact).where(HistoryFact.patient_id == patient_id))
    await db.execute(delete(IntakeForm).where(IntakeForm.patient_id == patient_id))
    await db.execute(delete(DiaryEntry).where(DiaryEntry.patient_id == patient_id))
    await db.execute(delete(DiaryTemplate).where(DiaryTemplate.patient_id == patient_id))
    await db.execute(delete(CalendarEvent).where(CalendarEvent.patient_id == patient_id))
    # a surviving feed would be a working PHI URL for an erased person (ADR-037)
    await db.execute(delete(CalendarFeed).where(CalendarFeed.patient_id == patient_id))
    await db.execute(delete(Share).where(Share.patient_id == patient_id))
    await db.execute(delete(ShareDecline).where(ShareDecline.patient_id == patient_id))
    await db.execute(delete(DocumentShareLinkItem).where(DocumentShareLinkItem.patient_id == patient_id))
    await db.execute(delete(DocumentShareLinkHandout).where(DocumentShareLinkHandout.patient_id == patient_id))
    await db.execute(delete(DocumentShareLink).where(DocumentShareLink.patient_id == patient_id))
    await db.execute(delete(DocumentReference).where(DocumentReference.patient_id == patient_id))
    # Crypto-shred (ADR-031): destroying the patient KEK renders every encrypted
    # blob / extracted_text / extraction_json unrecoverable, live and — as the
    # keystore's short-retention backup stream rolls — in backups too.
    from app.models.patient_key import PatientKey
    from app.core.patient_keys import invalidate as invalidate_kek
    await db.execute(delete(PatientKey).where(PatientKey.patient_id == patient_id))
    invalidate_kek(patient_id)
    await db.execute(delete(PatientAccess).where(PatientAccess.patient_id == patient_id))
    await db.execute(delete(PatientCaregiverInvite).where(PatientCaregiverInvite.patient_id == patient_id))
    from app.models.favorite import PatientFavorite
    await db.execute(delete(PatientFavorite).where(PatientFavorite.patient_id == patient_id))

    # Purge audit log entries for the patient row and all their clinical data rows
    pid_str = str(patient_id)
    all_entity_ids = (
        [pid_str]
        + doc_ids + cond_ids + med_ids + obs_ids
        + inc_ids + exp_ids + einst_ids + carer_ids + fact_ids + form_ids + diary_ids + cal_ids + feed_ids + rec_ids
        + share_ids + decline_ids + link_ids
    )
    await db.execute(delete(AuditLog).where(AuditLog.entity_id.in_(all_entity_ids)))

    # Delete patient row
    await db.execute(delete(Patient).where(Patient.id == patient_id))

    # Write tombstone — no PII, records that erasure occurred and who triggered it
    actor_name = " ".join(filter(None, [actor.first_name, actor.last_name])) or actor.email
    db.add(AuditLog(
        timestamp=datetime.now(UTC),
        user_id=actor.id,
        user_name=actor_name,
        entity_type="Patient",
        entity_id=pid_str,
        action="erased",
        changes=None,
    ))

    # Delete storage files before committing — if this fails, rollback
    storage = get_storage()
    try:
        for path in storage_paths:
            storage.delete(path)
    except Exception as exc:
        await db.rollback()
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage deletion failed; erasure aborted.",
        ) from exc

    await db.commit()


async def erase_user(
    user_id: uuid.UUID,
    actor: User,
    db: AsyncSession,
) -> None:
    """Anonymise a User record and remove all credentials and access grants.

    Blocked if the user still owns non-deleted Patients.
    """
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted == False)  # noqa: E712
    )
    target = result.scalar_one_or_none()
    if not target:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Block while the user is the last admin-level grant holder of any Patient (ADR 026)
    from app.models.access import PatientAccess

    held = await db.execute(
        select(PatientAccess.patient_id).where(
            PatientAccess.user_id == user_id,
            PatientAccess.access_level == "admin",
            PatientAccess.revoked_at == None,  # noqa: E711
            PatientAccess.is_deleted == False,  # noqa: E712
        )
    )
    sole_ids = []
    for (pid,) in held.all():
        others = await db.execute(
            select(PatientAccess.id).where(
                PatientAccess.patient_id == pid,
                PatientAccess.user_id != user_id,
                PatientAccess.access_level == "admin",
                PatientAccess.revoked_at == None,  # noqa: E711
                PatientAccess.is_deleted == False,  # noqa: E712
            )
        )
        if others.first() is None:
            sole_ids.append(str(pid))
    if sole_ids:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "User is the last admin-level caregiver of these Patients — grant someone else admin access or erase them first.",
                "patient_ids": sole_ids,
            },
        )

    # Hard-delete credentials and access grants
    from app.models.governance import ConsentRecord
    await db.execute(delete(PasskeyCredential).where(PasskeyCredential.user_id == user_id))
    await db.execute(delete(GroupMembership).where(GroupMembership.user_id == user_id))
    await db.execute(delete(PatientAccess).where(PatientAccess.user_id == user_id))
    # their subscriptions die with the access they rode on (ADR-037)
    await db.execute(delete(CalendarFeed).where(CalendarFeed.user_id == user_id))
    await db.execute(delete(ConsentRecord).where(ConsentRecord.user_id == user_id))
    from app.models.favorite import PatientFavorite
    await db.execute(delete(PatientFavorite).where(PatientFavorite.user_id == user_id))

    # Scrub user_name from existing audit entries — keep the UUID for referential integrity
    await db.execute(
        update(AuditLog)
        .where(AuditLog.user_id == user_id)
        .values(user_name="[erased]")
    )

    # Anonymise PII fields; keep UUID shell for audit references
    target.email = f"erased+{user_id}@erased.invalid"
    target.hashed_password = ""
    target.recovery_code_hash = None  # a credential like any other (ADR 044)
    target.first_name = None
    target.last_name = None
    target.is_active = False
    target.is_deleted = True

    # Write tombstone
    actor_name = " ".join(filter(None, [actor.first_name, actor.last_name])) or actor.email
    db.add(AuditLog(
        timestamp=datetime.now(UTC),
        user_id=actor.id,
        user_name=actor_name,
        entity_type="User",
        entity_id=str(user_id),
        action="erased",
        changes=None,
    ))

    await db.commit()
