# ADR 008 — Mass upload: no Batch entity

**Status:** Accepted

## Context

Users onboarding an existing Patient (one who already has many paper documents) need a way to upload dozens of files in one action rather than one at a time. The question was whether to introduce a `Batch` as a first-class database entity (with its own ID, persistent status, and progress) or treat bulk upload as a pure UI convenience where each Document remains independent.

## Decision

No `Batch` entity. Each uploaded Document is created independently using the existing single-document upload endpoint. The UI sends files in small parallel groups (up to 4 concurrent), tracks upload progress in local component state, and auto-refreshes the document list when all uploads finish. A "Retry failed" button re-queues any files that failed to upload.

The approach mirrors paperless-ngx's bulk upload model.

## Consequences

- No new database table or migration required.
- Upload progress is ephemeral — if the user closes the tab mid-upload, progress is lost (files already uploaded are safe; the rest must be re-uploaded).
- "Retry all failed" for pipeline-processing failures (after upload) is handled separately via the existing per-document retry endpoint, surfaced as a bulk "Retry N failed" button on the documents page.
- If persistent batch tracking (upload history, resumable uploads) is needed in the future, a `Batch` entity and a new upload endpoint would be the natural extension point.
