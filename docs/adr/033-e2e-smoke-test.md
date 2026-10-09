# ADR 033: E2E smoke test, not a frontend regression suite

**Status:** Accepted

## Context

Frontend CI ran `tsc --noEmit`, `next build` and `pnpm audit` — and nothing else. Five consecutive bug-fix commits (a `<div>` inside a `<ul>`, a `<ul>` inside a `<ul>`, a `loading.tsx` that froze navigation, a theme script that deleted React's meta tags) were all green on every one of those checks. They were hydration and navigation failures: the code compiled, the server returned HTTP 200 with complete HTML, and the app was dead in the browser — typically from the *second* click onwards.

No check in the pipeline could see that class of failure, because seeing it requires a real browser.

The backend already has the regression suite (~20 pytest files against a real Postgres) and owns the domain logic and the security rules — grants, erasure cascade, admin-has-no-clinical-access. Duplicating that surface in the frontend would mean maintaining a second suite for bugs the first one already catches.

## Decision

One Playwright smoke test (`frontend/e2e/smoke.spec.ts`), blocking on every PR.

- **Path:** log in with the seeded admin → land on the patients list → open a patient → **click a second time** in the sidebar. The second click is the point: a test that clicks once stayed green through all five bugs.
- **Failure condition:** any `console.error` or unhandled page exception fails the test. Hydration mismatches surface *only* there, never in the HTTP status or the DOM assertion.
- **Target:** the production build (`next build && next start`), not `next dev` — dev-only warnings would drown the console-error signal, and the production build is what users get.
- **Stack:** Postgres + Redis as CI services, backend and frontend as plain processes in the Playwright container. No Docker-in-Docker, no compose — it mirrors the existing `backend` job, which is known to work on the runner.
- **Fixture:** the existing `POST /api/dev/seed` (dev-only endpoint). Nothing new to build. It seeds `admin@openavisio.dev` plus a Demo Patient with an *explicit grant* — the `admin` role alone confers no clinical access (ADR 025).
- **Not path-filtered, not nightly.** Login runs through backend sessions and auth middleware, so a backend-only change can break it without touching a frontend file. And a test that blocks nothing prevents nothing.

## Consequences

**Good:**
- The exact bug class that produced five commits now turns a PR red instead of reaching production
- Roughly 25 lines of test, one config file, one new dev-dependency; no mock backend to keep in sync with the real one (it is always the mock that drifts, and a lying mock turns the test green while the app is broken)
- Runs parallel to the `backend` and `frontend` jobs, so wall-clock only grows if it becomes the slowest job

**Trade-off:**
- Deliberately **not** covered: AI chat and document extraction (they need aiservice and a Celery worker — slow and flaky in CI), the role matrix, i18n locale switching, mobile viewport, passkeys
- The `@playwright/test` version is pinned exactly (no `^`) because the CI image tag must match it; upgrading means editing both
- The console-error rule can be loud. Genuine errors get fixed; anything excluded is excluded **by name, with a reason** — never a blanket regex, which would switch off the sensor the suite is built around

The suite grows with the app: when a change touches a flow the smoke test walks through, the test gets adjusted or extended in the same commit.
