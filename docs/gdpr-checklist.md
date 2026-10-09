# GDPR checklist for new features

Run this checklist before merging any feature that stores, processes, displays, or transmits personal data. "Personal data" in OpenAvisio means anything linked to a Patient or User — clinical data, documents, health logs, messages, access records, audit entries.

## 1. Data minimisation (Art. 5(1)(c))

- [ ] Does the feature collect only the data it actually needs?
- [ ] Are optional fields truly optional in the schema?

## 2. Purpose limitation (Art. 5(1)(b))

- [ ] Is the purpose of the new data clearly scoped?
- [ ] Could the data be misused for a purpose the user didn't consent to?

## 3. Right to erasure (Art. 17)

- [ ] If the feature introduces a new table or entity linked to a Patient, is it included in `services/erasure.py → erase_patient()`?
- [ ] If the feature introduces a new table or entity linked to a User, is it included in `erase_user()`?
- [ ] Does the FHIR export in `routers/export.py` need updating to include the new entity?

## 4. Data portability (Art. 20)

- [ ] If the feature stores new patient data, add a corresponding FHIR resource to `GET /patients/{id}/export/fhir`.

## 5. Audit logging (Art. 5(2) accountability)

- [ ] Does the feature create, update, or delete personal data? If so, does it write an `AuditLog` entry?

## 6. Access control

- [ ] Is the new endpoint protected by `require_patient_access` or `require_admin`?
- [ ] Does the feature respect the existing Caregiver / Coordinator / admin role hierarchy?

## 7. Third-party data flows (Art. 28)

- [ ] Does the feature send personal data to an external service?
- [ ] If yes: is there a DPA with that service? Is it listed in the RoPA (`docs/ropa.md` once written)?

## 8. Security (Art. 32)

- [ ] Are new API inputs validated at the boundary?
- [ ] Does the feature store files? If so, are they encrypted via `core/encryption.py`?
- [ ] Does the feature log anything that could contain PII? Ensure PII is excluded from log output.

## 9. Special-category data (Art. 9)

OpenAvisio processes health data, which is special-category under Art. 9. Any feature that extends the clinical data model (new entity types, new fields on existing entities) must be reflected in the DPIA (`docs/dpia.md` once written).

---

## Quick reference — where to look

| Concern | File |
|---|---|
| Erasure | `backend/app/services/erasure.py` |
| FHIR export | `backend/app/routers/export.py` |
| Encryption | `backend/app/core/encryption.py` |
| Access control | `backend/app/auth/access.py` |
| Audit logging | `backend/app/core/audit.py` |
| Security ops | `docs/security.md` |
| ADRs | `docs/adr/` |
