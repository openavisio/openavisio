# ADR 027: Legal representation is a flag on the access grant, not a separate entity

**Status:** Accepted (supersedes the representation model of ADR 003)

## Context

`PatientRepresentation` was a separate entity that did two things at once: it granted `full` clinical access to a linked user (a second, invisible access path in `resolve_patient_access`) and it flagged who could share externally (Regel X, ADR 021). It also carried compliance fields (court reference, scope, validity) and could describe an external person with no account.

Two problems. First, the auto-access contradicted ADR 025/026 — every other access path is now a visible, revocable grant; representation was a hidden one. Second, the UI showed it as a second "add a person" surface next to Caregivers, which was confusing and overlapped in effect.

Design session (2026-07-09): OpenAvisio's deployments (Verein, care home, families) will not record a legal representative who has *no* system access — legal reps are active participants with a login. That removes the only reason to keep a separate entity (account-less external reps).

## Decision

Legal representation becomes a boolean `is_legal_representative` on `PatientAccess`. A person's human relationship (Mother, Nurse, …) stays in the existing `relationship` field; the flag captures the legal standing independently, so "Mother who is also the guardian" is expressible.

- `resolve_patient_access` loses the representation branch — access is grants/groups only.
- Regel X (external sharing) reads the flag instead of the old table.
- `PatientRepresentation` and `RepresentationInviteToken` (model, router, schemas, the frontend subpage) are deleted. The `Legal Guardian`/`Power of Attorney` entries are removed from the relationship dropdown — the checkbox replaces them.

Dropped deliberately: court file reference, scope, valid-from/until. If a deployment later needs to document a court reference, it is a field on the grant — added when a real need appears.

## Migration

`w3r4s5t6u7v8`: add the flag; for every active representation with a linked user, flag their existing grant or create a full grant with the flag (nobody loses access, legal standing preserved); drop the two representation tables. Account-less external representations (none in practice) are not migrated.

## Consequences

- One surface for "who is involved with this patient": the Caregivers panel, with a "Legal rep" badge
- ADR 003's "legal representation is an attribute of a grant" is now literally true; its separate-entity implementation is retired
