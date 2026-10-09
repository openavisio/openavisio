# ADR 009 — Admin log viewer: SSE + Redis pub/sub + ring buffer

**Status:** Accepted

## Context

Admins need visibility into what the system is doing — particularly when a Document's Processing Pipeline fails. Without a log viewer, the only option is SSH into the server and tail logs manually. The feature needs to cover both application-level log output (FastAPI + Celery workers) and a Processing Pipeline task list (Document status, stage, error).

## Decision

**App logs** are delivered via SSE (`StreamingResponse` on `/api/admin/logs/stream`). A custom `logging.Handler` installed in both the FastAPI process and the Celery workers publishes log entries as JSON to a shared Redis pub/sub channel. The SSE endpoint subscribes to that channel and pushes entries to connected clients. An in-memory ring buffer (≈500 entries) in the FastAPI process provides page-load history so a freshly opened log page is not blank.

Log levels: root logger at INFO+; `app.*` and `celery.*` loggers at DEBUG. Third-party library noise (SQLAlchemy, httpx, etc.) is suppressed to WARNING.

**Processing Pipeline task list** is a polled REST endpoint returning the last 50 Documents ordered by `updated_at` DESC. No separate task table — Document already carries `processing_status`, `pipeline_stage`, and `processing_error`.

**Auth:** JWT token passed as a query parameter (`?token=<jwt>`), because the browser-native `EventSource` API cannot send custom headers. The token is admin-only and short-lived. Caddy log redaction is tracked in issue #16.

Both panels live on `/admin/logs` as two tabs: "Application Logs" and "Processing Pipeline".

## Considered options

- **WebSocket** — bidirectional, unnecessary for one-way log streaming; more complex to implement and proxy.
- **Next.js proxy for SSE** — avoids the token-in-query-param issue but adds latency, a streaming proxy layer, and complexity. Not worth it for an internal deployment.
- **Database table for log entries** — fully persistent but synchronous DB writes on every log line degrade pipeline throughput. Deferred to issue #14.
- **Dedicated TaskRun table** — covers all Celery jobs, not just document pipeline. Deferred to issue #15.

## Consequences

- Log entries are lost on FastAPI or Redis restart (ring buffer is in-memory; Redis pub/sub is ephemeral). Acceptable for the "what is happening right now" use case.
- Celery worker logs appear in the same stream as FastAPI logs because both publish to the same Redis channel — no need to aggregate log files from multiple processes.
- The task list reflects Document state, not raw Celery task state. Background jobs (embedding scheduler, diary embedding) are visible in the app log stream only, not the task list tab.
- **Caddy must route `/api/*` directly to `backend:8000`** (with `flush_interval -1` to disable buffering). If Caddy routes everything to the Next.js frontend, SSE and the tasks poll endpoint are unreachable from the browser because Next.js has no handler for those paths. The frontend-only Caddyfile default is a known misconfiguration risk.
