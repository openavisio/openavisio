# Consent-gated file sharing introduces a second, narrow access path

To let a research study or registry collect Patient files (e.g. EEG data for an epilepsy study), a Coordinator/admin creates a **Sharing Purpose** that broadcasts an org-wide ask, and a Caregiver responds by selecting Document(s) and consenting, which creates a **Share** — a consented link (Document × Sharing Purpose) that lets the Coordinator tier download just that file. This deliberately adds a **second access path alongside PatientAccess**, scoped to individual shared files and bound to a purpose, rather than the all-or-nothing PatientAccess that ADR-003 made the single tier.

## Why a second path (and not PatientAccess)

A Purpose Manager must see *only* the files explicitly shared for the study, never the rest of the Patient's record — exactly what PatientAccess cannot express (it is whole-record access). Routing study collection through PatientAccess would over-expose data and muddy the purpose-binding audit trail. ADR-003 collapsed access tiers to remove a *social-label* path (Family) that added no real access difference; this path is different in kind — it is genuinely narrower than PatientAccess, so it earns its place.

## Shape of the v1 model

- **Pull-only, broadcast.** A Sharing Purpose is org-wide; there is no per-Patient targeting (impractical at 100+ Patients) and no push direction.
- **Requests are derived, not materialised.** An open request is the absence of a response for a (Patient × Purpose). Only responses are stored — a Share (consent) or a decline marker. The Purpose's activation time records when everyone was asked; per-request proof is unnecessary for surveys.
- **Caregiver picks the files.** The ask names a *kind* of data ("EEG") in free text; the Purpose Manager never browses the vault. File selection and consent happen on the Patient side. Any User with Patient access may consent (self-confirmation allowed in v1); who consented and when is recorded.
- **Role-owned, not person-owned.** A Sharing Purpose belongs to the Organization; any Coordinator/admin can manage and download it, so staff turnover orphans nothing.
- **Identification mode.** Per Purpose: *identified* (name shown) or *anonymous* (stable per-Patient pseudonym only). Anonymity is metadata-only — file contents are never altered.
- **Lifecycle.** Open → closed (manual or expiry). Closing/expiry only stops *new* Shares; existing Shares stay downloadable while their Document exists. A Share's access ends on revoke or Document deletion. Patient Erasure cascades Shares and decline markers.
- **No download audit.** The consent record (Share) is the compliance trail; a closed Purpose implies the files were collected. Logging every download adds noise without value for surveys.

## v1 data model

Three new tables, all on `BaseModel` (`id`, `created_at`, `updated_at`, `is_deleted`). No `org_id` (single-org deployment) and no target column (org-wide broadcast).

```
sharing_purposes
  name                str
  description         text          free-text ask, e.g. "EEG recordings"
  identification_mode str            identified | anonymous
  status              str            open | closed
  expires_at          datetime?      optional auto-close
  closed_at           datetime?
  created_by_user_id  uuid? → users  accountability only; scrubbed to [erased] on User Erasure
  -- deliberately NO owner_id: role-owned (any Coordinator/admin), not person-owned

shares
  sharing_purpose_id  uuid → sharing_purposes
  document_id         uuid → document_references
  patient_id          uuid → patients        denormalised (= document.patient_id) for erasure + pseudonym grouping
  status              str            active | revoked
  consented_by_user_id uuid? → users
  consented_at        datetime
  consented_legal     bool           consenter held a legal-representation relationship at the time
  revoked_at          datetime?
  UNIQUE (sharing_purpose_id, document_id)

share_declines
  sharing_purpose_id  uuid → sharing_purposes
  patient_id          uuid → patients
  declined_by_user_id uuid? → users
  declined_at         datetime
  UNIQUE (sharing_purpose_id, patient_id)
```

- **Open requests are derived, not stored.** For a Patient P: every `sharing_purpose` that is `open` and not expired and has neither an active `share` nor a `share_decline` for (purpose, P). A response (first Share *or* a decline) clears the nudge; adding/revoking more files afterwards is a deliberate action on the patient page, not continued nudging.
- **Pseudonym is computed, not stored.** Anonymous mode shows a stable code derived from `hash(purpose_id + patient_id)`; the API simply omits the Patient name. No mapping table.
- **Download path is role-only.** A dedicated endpoint checks `role ∈ {manager, admin}` plus `share.status = active` and that the Purpose and Document still exist — it does **not** call `require_patient_access`. Decryption reuses the normal document download/decrypt service.
- **Revoke is a status change** (`status = revoked`, set `revoked_at`), not a delete — the consent history is preserved. Patient Erasure hard-deletes Shares and Share declines.
- **Audit** maps onto the existing `created|updated|deleted` vocabulary: Share created/declined → `created`; revoke/close → `updated`; entity types `Share`, `ShareDecline`, `SharingPurpose`. No per-download audit.

## Consequences

- Shared files are visible to the whole Coordinator/admin tier, not one person — acceptable for a small trusted board; the consent text says "with the study leadership", not a named person.
- Deferred to later stages: sharing **structured clinical data** (not just Documents); **email notification** of new Purposes (and a manual note that without SMTP configured, Purposes cannot be sent); **pseudonymisation hardening**; a **four-eyes** consent option; a dedicated "may create Purposes" permission decoupled from Coordinator.

See also ADR-003 (access model) and the **Data sharing** section of `CONTEXT.md`.
