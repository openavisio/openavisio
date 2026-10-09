# External document share links introduce a third, outbound access path

To let a Caregiver hand a new external specialist (a doctor or therapist not in the system) the Patient's existing medical history, a Caregiver selects one or more Documents and generates a **share link** — a time-limited, read-only, anonymous URL that grants access to exactly that set of Documents. This is a **third access path**: PatientAccess is whole-record access for accounts, ADR-020 Sharing is inbound study collection by internal staff, and this is **outbound push to an anonymous external reader**. Issue #12.

## Why a third path (and not PatientAccess or ADR-020 Sharing)

- **Not PatientAccess.** Granting a specialist a Caregiver account over-exposes the whole record and requires onboarding an external party into the system. The real need is lighter: read a fixed set of files, no account, for a bounded time.
- **Not ADR-020 Sharing.** That path is *pull-only, inbound, internal*: a Coordinator broadcasts an org-wide ask and internal staff download consented files, with **no download audit**. #12 is the opposite in every axis — *push, outbound, external*, and it **requires access auditing** (external disclosure of health data is exactly what accountability must capture). Its `Share` row is bound NOT-NULL to a `SharingPurpose` with a `UNIQUE(purpose, document)` constraint; reusing it would mean nulling the FK and dropping the constraint, breaking the study-sharing invariants. The two paths stay separate by design (see ADR-020).

## Shape of the v1 model

- **Anonymous link, hardened.** Whoever holds the URL can read it — no account, no login. The sensitivity-vs-convenience tradeoff is deliberate and mitigated: 256-bit token, only its hash stored, short expiry, revocation, per-access audit, `no-referrer` / `noindex` / `no-store` headers, constant "invalid" response.
- **Set of Documents, snapshot + append.** A link grants a fixed, explicitly-chosen set (a new specialist typically needs the whole prior history, not one file). The set is a **snapshot** — future uploads never appear automatically (consent cannot cover data that did not yet exist) — but a Caregiver may **append** more Documents to an existing link as a deliberate, audited action.
- **Push, copy-delivered.** The Caregiver copies the link and sends it through their own channel. The full token is shown **once** at creation (only its hash persists); the management view thereafter shows "active until {date}" without the token. App-sent email is deferred.
- **Outbound sharing is a data-subject act, not a staff act.** Creating a link requires `role = user` with concrete Patient access, **or** being the Patient's owner / active legal representative (which may hold regardless of role). A `manager`/`admin` acting only on blanket/staff access is refused (403): staff must not broker external disclosure of a Patient they merely administer. A parent who happens to also be the deployment admin can still share their own child's files (owner/representative exception).
- **Full clinical context to the reader.** The reader sees the Patient name, date of birth, and Org name (a treating specialist must know whose record this is — pseudonymisation would be clinically dangerous), plus, per Document, the PDF viewer + Summary + that Document's own extracted clinical data. Hard read-only (no edit/verify controls, no patient-wide navigation); original-file download is allowed and audited; raw OCR text is not shown.
- **Bounded lifetime.** Expiry is one of 7 / 30 / 90 days (default 30, max 90); there is no "never expires". Expired or revoked → `410 Gone` with a clear message; unknown/malformed token → `404`. A Document dropping out of the set (soft-delete) removes it from the view; when all Documents are gone the link returns 410. Patient Erasure cascades the link, its items, and its access-audit entries.

## v1 data model

Two new tables on `BaseModel` (`id`, `created_at`, `updated_at`, `is_deleted`). No `org_id` (single-org deployment).

```
document_share_links
  patient_id          uuid → patients            denormalised (for erasure cascade + access checks)
  token_hash          str                         SHA-256 of the URL token; plaintext token never stored
  status              str                         active | revoked
  expires_at          datetime                    NOT NULL; 7/30/90 days from creation, max 90
  created_by_user_id  uuid? → users               who created the link; scrubbed to [erased] on User Erasure
  created_legal       bool                        creator held a legal-representation relationship at the time
  revoked_at          datetime?

document_share_link_items
  share_link_id       uuid → document_share_links
  document_id         uuid → document_references
  patient_id          uuid → patients            denormalised (= document.patient_id) for erasure
  UNIQUE (share_link_id, document_id)
```

- **Token is verified by hash.** The public endpoint hashes the URL token and looks up `token_hash` (indexed); any miss — bad format, unknown, wrong — yields the same `404`, so the endpoint never reveals which links exist. A leaked DB dump contains no usable tokens.
- **Access path is token-only.** A dedicated **public** endpoint (`/api/public/document-shares/{token}`, public by simply omitting the `get_current_user` dependency — this backend authenticates per endpoint, and `CORSMiddleware` is the only middleware it has) checks `status = active`, `expires_at > now`, and that the Document still exists — it does **not** call `require_patient_access`. Decryption reuses the normal envelope-decrypt service.
- **Append is additive**; adding a Document to an existing link does not change its expiry.
- **Revoke is a status change** (`status = revoked`, set `revoked_at`), not a delete. Patient Erasure hard-deletes links and items.
- **Audit extends the vocabulary with `accessed`.** Link created/appended → `created`; revoke → `updated`; each read of a Document via a link → a per-access entry `action = accessed`, `entity_type = DocumentShareLink`, `user_id = null`, `user_name = "External via share link"`, with `ip_address` + `user_agent`, `changes = {document_id, event: view|download}`. Access logging is **debounced** (one entry per link+Document per ~10 min) so a PDF viewer's range requests do not flood the log. This is the deliberate inverse of ADR-020's no-download-audit: external disclosure must be provable. Patient Erasure purges these entries with the rest of the Patient's audit history (consistent with ADR-017 / `services/erasure.py`), leaving only the tombstone.

## Consequences

- The anonymous link is the highest-sensitivity surface in the app: interception exposes an identified person's health data. Mitigations (short expiry, revoke, hashing, headers, audit) manage but do not eliminate this — accepted for the convenience of account-free specialist access.
- The recipient's IP address and user-agent are themselves personal data of the specialist; this new processing is recorded in DPIA/RoPA and `docs/security.md`.
- App-level rate limiting is out of scope for v1 (relies on the reverse proxy); a project-wide rate-limiting + hardening effort is planned separately.
- Deferred to later stages: **app-sent email delivery** of links (address validation + delivery audit); **live** (non-snapshot) sets; **per-link download disable**; **watermarking**.

See also ADR-003 (access model), ADR-017 (patient erasure cascade), ADR-020 (inbound consent-gated sharing), and the **Data sharing** section of `CONTEXT.md`.
