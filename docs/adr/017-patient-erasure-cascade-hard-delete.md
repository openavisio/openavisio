# ADR 017: Patient erasure uses cascade hard delete, not anonymisation

**Status:** Accepted

## Context

GDPR Article 17 (right to erasure) requires that a Patient's personal data be removed on request. The current soft-delete implementation (`is_deleted = True`) does not satisfy this — the data remains in the database.

Two strategies were considered:

### Option A — Anonymisation

Null out personally identifying fields on the Patient row (name, date of birth, contact details) while retaining clinical data rows (Diagnoses, Medications, Observations, etc.) linked to a pseudonymous ID. Common in SaaS platforms where aggregate data has independent value.

**Rejected.** Health data is special-category data under GDPR Article 9. In OpenAvisio, the clinical records (seizure Incidents, Diagnoses, Medications, DiaryEntries) are the entire purpose of the Patient record — they cannot be dissociated from the identity. A pseudonymous Patient row linked to 50 lab results and a seizure history remains a personal record and does not satisfy erasure. Anonymisation would provide legal cover in name only.

### Option B — Cascade hard delete ✓

Delete the Patient row and all linked clinical data: Conditions, MedicationStatements, Observations, Incidents, DiaryEntries, CalendarEvents, DocumentReferences (including physical storage files), DocumentChunks (embeddings), Recommendations, ChatMessages, PatientRepresentations, PatientAccess grants, and PatientCaregiverInvites. Purge all prior AuditLog rows for that Patient's data. Write a single tombstone AuditLog entry (no PII).

**Accepted.** For a health vault, the clinical record is the identity. Hard delete is the only path that genuinely satisfies Article 17.

## Consequences

- Erasure is irreversible. No recovery path exists once the operation completes.
- Storage files (PDFs, images) are deleted synchronously as part of the same operation. If storage deletion fails, the database transaction rolls back.
- The tombstone AuditLog entry records: `entity_type=Patient`, `entity_id=<uuid>`, `action=erased`, `user_name=<who triggered it>`, `changes=null`.
- Correspondents are organisation-scoped and are not deleted — they may be referenced by other Patients' Documents.
- Exposed via `POST /patients/{patient_id}/erase`, separate from the existing soft-delete `DELETE /patients/{patient_id}`.
