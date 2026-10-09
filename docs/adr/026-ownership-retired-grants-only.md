# ADR 026: Ownership retired — PatientAccess grants are the only clinical access path

**Status:** Accepted

## Context

ADR 025 closed the role-based bypass, but a second implicit access path remained: whoever creates a Patient becomes `owner_id` — permanent admin-level access, invisible in the access panel, irrevocable (no transfer mechanism existed). In the hosted scenario this recreates the #65 problem operationally: staff who onboard patients as a service keep full clinical access forever. ADR 003 declared PatientAccess the single access tier; ownership was a hidden second one.

Design sessions (2026-07-09) walked homelab, hosted/Verein, and care-home scenarios. Finding: the difference between "creator keeps access" (homelab parent-admin, care-home coordinator) and "creator must not keep access" (hosting staff) is not a role or deployment property — it is whether the creator belongs to the care circle. One mechanism covers all cases if creation confers a *normal, visible, revocable grant*.

## Decision

- `owner_id` becomes `created_by`: pure audit metadata, never access-relevant. The term **Owner is retired** from the domain language.
- Creating a Patient auto-creates a regular **admin-level PatientAccess grant** for the creator — first entry in the access panel, revocable like any other.
- Roles gate capabilities only: `admin` = system administration + everything manager can; `manager` (Coordinator) = create Patients, Sharing Purposes, Groups; `user` = purely grant-based. No role ever confers clinical access (ADR 025).
- **Handover** (hosting case): when an invite-based admin-level grant is accepted, the system offers the inviter a one-click "complete handover — remove your own access?". Otherwise visibility is the safeguard: caregivers see and can remove staff grants themselves.
- **Last-grant rule:** the last admin-level grant of a Patient cannot be revoked (no orphaned records).
- **Erasure re-anchoring:** Patient Erasure may be triggered by any admin-level grant holder. User Erasure is blocked while the User is the *last* admin-level grant holder of any Patient — the built-in escape is granting someone else admin level (the transfer that ownership never had).
- Group management ("add Patient to Group") requires an admin-level grant on the Patient (was: owner check). Care-home team access = a Group (e.g. "all residents") with coordinators as admin-level members — no role path.
- Notification recipients re-anchor from `owner_id` to admin-level grant holders.

## Migration

Alembic data migration backfills an admin-level grant for every existing `owner_id`, then renames the column to `created_by`. Nobody loses or gains access; the invisible path becomes visible and revocable. The rename intentionally breaks all remaining `owner_id` code references so none can be missed.

## Consequences

- Group role names (`viewer/editor/admin/owner`) now contain a misleading "owner" — rename tracked as follow-up
- The access panel becomes the single source of truth a caregiver can read: every person with access to their record is listed there, staff included
