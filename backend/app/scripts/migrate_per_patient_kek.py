"""Big-bang migration to per-patient KEK envelope encryption (ADR-031, #76).

Converts the legacy scheme (document DEK wrapped under the master KEK; plaintext
extracted_text / extraction_json / chunk content) to the per-patient hierarchy:

    * one KEK per patient, wrapped under the master KEK, in `patient_keys`
    * each document DEK re-wrapped under its patient's KEK
    * extracted_text / extraction_json / document-chunk content encrypted under
      the document DEK's patient KEK

OFFLINE (ADR-031): stop backend + celery first. Idempotent — already-migrated
rows are detected and skipped, so a re-run after a crash is safe.

    1. Stop backend + celery.
    2. alembic upgrade head            # creates patient_keys
    3. python -m app.scripts.migrate_per_patient_kek --confirm-services-stopped
    4. Start backend + celery.
"""

import argparse
import asyncio
import json
import os
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.encryption import _STR_PREFIX, _get_kek, encrypt_str, unwrap_dek, wrap_dek
from app.models.chat import ChatMessage, DocumentChunk
from app.models.diary import DiaryEntry
from app.models.document import DocumentReference
from app.models.patient import Patient
from app.models.patient_key import PatientKey


async def _patient_kek(db, master, patient_id) -> bytes:
    """Return the unwrapped KEK for a patient, creating the row on first use."""
    row = (await db.execute(select(PatientKey).where(PatientKey.patient_id == patient_id))).scalar_one_or_none()
    if row is not None:
        return unwrap_dek(row.wrapped_kek, master)
    kek = os.urandom(32)
    db.add(PatientKey(patient_id=patient_id, wrapped_kek=wrap_dek(kek, master), kek_version=1))
    await db.flush()
    return kek


def _is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(_STR_PREFIX)


async def migrate() -> None:
    master = _get_kek()
    docs_done = chunks_done = keks = notes_done = msgs_done = 0

    async with AsyncSessionLocal() as db:
        patients = (await db.execute(select(Patient.id))).scalars().all()
        for pid in patients:
            kek = await _patient_kek(db, master, pid)
            keks += 1

            docs = (await db.execute(
                select(DocumentReference).where(DocumentReference.patient_id == pid)
            )).scalars().all()
            for doc in docs:
                # DEK: re-wrap master->patient. Detect by trying the master unwrap;
                # if it fails, the DEK is already patient-wrapped -> skip.
                if doc.encrypted_dek:
                    try:
                        dek = unwrap_dek(doc.encrypted_dek, master)
                        doc.encrypted_dek = wrap_dek(dek, kek)
                    except Exception:
                        pass  # already under the patient KEK
                if doc.extracted_text and not _is_encrypted(doc.extracted_text):
                    doc.extracted_text = encrypt_str(doc.extracted_text, kek)
                ej = doc.extraction_json
                if ej is not None and not _is_encrypted(ej):
                    # legacy JSONB dict -> encrypted JSON string
                    doc.extraction_json = encrypt_str(json.dumps(ej), kek)
                docs_done += 1

            # all chunks (document + diary) carry the same free text
            chunks = (await db.execute(
                select(DocumentChunk).where(DocumentChunk.patient_id == pid)
            )).scalars().all()
            for ch in chunks:
                if ch.content and not _is_encrypted(ch.content):
                    ch.content = encrypt_str(ch.content, kek)
                    chunks_done += 1

            # diary free-text notes
            entries = (await db.execute(
                select(DiaryEntry).where(DiaryEntry.patient_id == pid)
            )).scalars().all()
            for e in entries:
                for f in ("general_notes", "nutrition_notes"):
                    v = getattr(e, f)
                    if v and not _is_encrypted(v):
                        setattr(e, f, encrypt_str(v, kek))
                        notes_done += 1

            # chat messages
            msgs = (await db.execute(
                select(ChatMessage).where(ChatMessage.patient_id == pid)
            )).scalars().all()
            for m in msgs:
                if m.content and not _is_encrypted(m.content):
                    m.content = encrypt_str(m.content, kek)
                    msgs_done += 1

        await db.commit()

    print(
        f"Migrated {keks} patient KEK(s), {docs_done} document(s), {chunks_done} chunk(s), "
        f"{notes_done} diary note(s), {msgs_done} chat message(s)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate to per-patient KEK encryption (ADR-031).")
    parser.add_argument(
        "--confirm-services-stopped",
        action="store_true",
        help="Assert backend + celery are stopped. The migration refuses to run without it.",
    )
    args = parser.parse_args()
    if not args.confirm_services_stopped:
        print(
            "ERROR: refusing to migrate while services may be running.\n"
            "Stop backend + celery, run 'alembic upgrade head', then re-run with "
            "--confirm-services-stopped.",
            file=sys.stderr,
        )
        sys.exit(1)
    asyncio.run(migrate())


if __name__ == "__main__":
    main()
