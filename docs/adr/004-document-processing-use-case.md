# ADR 004: Document upload Processing Pipeline — scope and acceptance model

The Processing Pipeline extracts appointments, a summary, and referenced clinicians from uploaded Documents. Extracted appointments are proposed Events that require explicit Caregiver acceptance before appearing on the health timeline — they are never auto-created, whether the date is in the past or the future. Accepted appointments are materialised as `CalendarEvent` rows by the existing verify endpoint (`POST /documents/{id}/verify`), consistent with how Diagnoses, Medications, and Observations are already handled.

## Considered options

**Auto-create past appointments.** A date found in a report for a past appointment could be treated as historical fact and created unconditionally. Rejected: misparses and cross-patient references in the document text make silent auto-creation unsafe for a health record.

**Write proposed Events to `calendar_events` with `status="proposed"` during pipeline.** This would make proposals queryable and visible as greyed-out items before acceptance. Rejected for the initial implementation — it pollutes the calendar with unreviewed AI output and adds complexity without a clear user need. Can be revisited if the frontend needs a "pending proposals" view.

**No Correspondent model yet.** Documents reference clinics, labs, and individual doctors. A full model would need to represent both the institution and the person(s) behind it, with a relationship between them. That person↔institution distinction makes a flat correspondent model wrong and a two-level model non-trivial. Decision: `mentioned_persons` stays as unstructured metadata in `extraction_json`, displayed read-only in the verify screen. A dedicated Correspondent feature can be designed once the UI needs are clearer.

## Scope of the initial implementation

- Extraction prompt updated to include `mentioned_persons` (referenced clinicians and institutions, stored in `extraction_json`, no access-control implications).
- `ExtractionSummary` schema extended with `summary` and `mentioned_persons`.
- Verify endpoint extended to create `CalendarEvent` rows (with `source="pipeline"`) from the Caregiver-accepted subset of `extraction_json.appointments`.
- Verify frontend: summary and mentioned persons shown read-only; Diagnoses, Medications, Observations, and Appointments shown with per-item checkboxes; only checked items are sent to `POST /documents/{id}/verify`.
