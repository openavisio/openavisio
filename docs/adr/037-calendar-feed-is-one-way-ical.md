# The calendar feed is a one-way iCal subscription, not a two-way sync

A tester asked to have a Patient's appointments in their own calendar (Google, Outlook, Apple). OpenAvisio serves this as a **subscribable iCal feed**: an anonymous, token-authenticated URL returning `text/calendar`, which all three platforms subscribe to natively. There is no OAuth, no per-provider integration, and no write path back into OpenAvisio.

## Why one-way, and why no provider integrations

- **Two-way sync is three protocols, not one feature.** Google Calendar API, Microsoft Graph, and — for Apple — CalDAV with app-specific passwords, which has no OAuth flow at all. Each brings token refresh, quota handling, and conflict resolution between an appointment extracted from a doctor's letter and one edited on a phone. That is a permanent maintenance surface, and none of it serves the request.
- **The request was "show me the appointments", not "let me edit them".** A subscription satisfies it completely. Appointments originate in documents and are curated in OpenAvisio; the external calendar is a view.
- **iCal is a native platform feature.** One endpoint emitting a text format covers all three targets. Adding a provider costs nothing because there are no providers.

## Shape of the v1 model

- **One feed per Caregiver per Patient**, not one per Patient. Feeds are personal so they can be revoked personally — see the access check below.
- **Anonymous, token-authenticated**, following ADR-021: 256-bit token, only its SHA-256 hash stored, plaintext shown once at creation and thereafter living solely in the subscriber's calendar client.
- **No expiry.** ADR-021 links expire because they are a bounded disclosure to an outside specialist. A family calendar that silently stops updating after 30 days is a missed appointment, not a safety feature. Lifetime is bounded by revocation instead.
- **Revocation is inherited, not managed.** The feed endpoint checks that the stored `user_id` still holds live `PatientAccess` (not revoked, not expired). Removing a Caregiver from the care circle therefore kills their feed with no separate action — the failure mode where a departed Caregiver keeps receiving appointments cannot occur by forgetting a step.
- **Appointments only.** `category = "appointment"`; Milestones (ADR/issue #11 developmental milestones) are not calendar entries and are excluded. There is no appointment sub-type in the model and none is introduced — a taxonomy invented before anyone knows which types users separate would be the wrong taxonomy.
- **Full titles, disclosed.** The feed carries the real title, provider and location. A feed reading only "Termin" is worthless to the caregiver. Because those values are then stored on Google's or Microsoft's servers, feed creation states this in plain language in the UI; it is the user's decision to make, made knowingly.
- **Rolling window: future appointments plus 90 days back.** All history would export a full treatment chronology into a third-party cloud for no benefit; future-only makes last week's appointment vanish at midnight, which reads as a broken calendar. 90 days is a judgement call, held as one named constant.

## Times are floating, deliberately

`calendar_events.start_at` is a `String(50)` holding either a bare ISO date (`2026-03-14`) or a naive local timestamp (`2026-03-14T09:30:00`, produced by `routers/documents.py`). No timezone is recorded anywhere on the event.

Date-only events are emitted as `VALUE=DATE` all-day entries, where the question does not arise. Timestamps are emitted as **floating time** — `DTSTART:20260314T093000`, no `Z`, no `TZID` — which the subscriber's calendar interprets in its own timezone.

The alternatives were rejected:

- **Reading a timezone from the document.** Medical letters state "9:30 Uhr" and never a timezone. Deriving one from the clinic address is inference, which `prompts/extraction.md` forbids by design, and it is wrong for telemedicine.
- **A per-Deployment timezone** (the `TZ` variable in `deploy/docker-compose.prod.yml`). An Organization is not necessarily co-located: `CONTEXT.md` admits a household or an association whose member families are scattered across regions. One timezone for the Deployment would be wrong for half of them.

Floating time is correct whenever the Caregiver is in their Patient's timezone, which is the normal case for someone providing day-to-day care, and it self-adapts across a scattered Organization with no configuration. **The known ceiling:** a Caregiver travelling outside their Patient's timezone sees the appointment at the wrong instant. The upgrade path is a timezone on the Patient (the feed is per-Patient already, so the endpoint changes and nothing else does). Marked with a `ponytail:` comment at the emitting code.

## v1 data model

One new table on `BaseModel` (`id`, `created_at`, `updated_at`, `is_deleted`).

```
calendar_feeds
  patient_id        uuid → patients     denormalised, for erasure cascade + access checks
  user_id           uuid → users        whose PatientAccess gates the feed
  token_hash        str                 SHA-256 of the URL token; plaintext never stored
  revoked_at        datetime?           explicit revocation; no expires_at by design
  last_accessed_at  datetime?           so a stale feed is visible in the UI
```

- **Token verified by hash**, indexed; any miss yields the same `404`, so the endpoint never reveals which feeds exist.
- **Public endpoint** (`/api/public/calendar/{token}.ics`) simply omits the `get_current_user` dependency — this codebase authenticates per endpoint, not in middleware, so "public" is the absence of that dependency and nothing else. It does not call `require_patient_access`; it resolves the feed by token hash, then loads the stored user and verifies their grant with `resolve_patient_access` directly.
- Serves `no-referrer`, `noindex`, `no-store`, matching ADR-021.

## Consequences

- **PHI leaves the deployment by design.** Appointment titles naming a Patient's specialists sit on Google's or Microsoft's servers for as long as the subscription lives, and may persist in their caches after revocation. This is disclosed at creation and is the user's choice; it is recorded in DPIA/RoPA and `docs/security.md`.
- **Erasure must cascade.** `calendar_feeds` is added to `services/erasure.py` for both Patient Erasure and User Erasure. A feed surviving a Patient Erasure would be a live PHI URL for an erased person — the defect this ADR most needs to prevent. The Erasure definition in `CONTEXT.md` is updated to name the table.
- **Not a governance category.** `services/governance.py` registers *clinical* tables for retention purging, keyed on a clinically relevant date. `DocumentShareLink` is deliberately absent from it and `CalendarFeed` follows: an access credential has no clinical date to measure retention against, and it is already destroyed by erasure and by revocation.
- **Revocation is not retraction.** Revoking stops future fetches; events already pulled into the subscriber's calendar remain there. Nothing in an iCal subscription can undo that.
- Deferred: two-way sync (rejected, not deferred), appointment type filters, per-Patient timezone, alarms/`VALARM` in the feed (OpenAvisio already has its own `reminder_sent_at` path).

See also ADR-021 (external document share links — the token pattern this follows), ADR-017 (patient erasure cascade), ADR-003 (access model).
