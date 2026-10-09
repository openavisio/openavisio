# ADR 025: Admin/manager roles have no blanket clinical access

**Status:** Accepted

## Context

`resolve_patient_access()` short-circuited for the `admin` role: unconditional full access to every Patient's record, before any ownership/grant check. Found in practice (issue #65): a deployment admin could open every patient and read all clinical data. This contradicted the boundary the system already drew elsewhere — ADR 021 ("Regel X": staff acting in admin/manager capacity are not Caregivers and cannot create share links) and the Sharing Purpose definition (managing one grants access to explicitly shared files, "nothing else in a Patient's record") — and undermined the core promise for hosted Deployments: the operator's IT admin must not be able to read medical records.

An audit showed nothing legitimate depended on the bypass: Coordinators (`manager` role) never had one and work via ownership + PatientAccess grants; Patient Erasure requires owner or an admin-level grant; user management uses `require_admin` role checks, not patient access.

## Decision

System roles (`admin`, `manager`) confer **zero** clinical data access. `resolve_patient_access()` resolves only ownership, group membership, legal representation, and PatientAccess grants. Administrative capability (user management, org settings, logs, license) stays behind role checks on the admin endpoints.

An admin who is also a parent/caregiver (common in homelab deployments) sees their own Patients through ownership/grants like any other User.

## Consequences

- Staff without a grant now get 404 on all patient/clinical endpoints (no existence leak; previously share-link creation leaked 403)
- The patients list is empty for pure staff accounts — administration that needs patient *existence* metadata must go through dedicated admin endpoints with explicit justification, none of which exist today (add deliberately, never via access-level bypass)
- Regression guard: `tests/test_admin_no_clinical_access.py`
