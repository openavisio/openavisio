# ADR 010 — NEXT_PUBLIC_* vars must be injected at build time via Docker build args

**Status:** Accepted, and no longer binding in practice (amended 2026-08-27)

> **Amended 2026-08-27.** The mechanism below is still correct for any
> `NEXT_PUBLIC_*` variable, and it is still the reason not to introduce one.
> **There are none left.** Nothing in `frontend/src` reads a `NEXT_PUBLIC_*`
> value; the SSE log viewer that motivated this ADR now goes through the server
> side. The `ARG`/`ENV` pair in `frontend/Dockerfile`, the `build.args` block in
> `docker-compose.prod.yml` and the `set_env` line in `setup.sh` were dead, and
> are gone.
>
> That matters beyond tidiness. The consequence stated below, "a production image
> built for openavisio.org cannot be redeployed to a different domain without a
> rebuild", is exactly what would have made one prebuilt frontend image per
> release impossible, and it is what ADR 045 and avisiohub ADR 0007 depend on
> ("with a registry there is no build, only a pull"). The frontend image is now
> domain-independent: the domain reaches it through `NEXTAUTH_URL` and `API_URL`,
> both ordinary runtime environment variables.
>
> If a `NEXT_PUBLIC_*` variable is ever genuinely needed, read this ADR first and
> then read it again: adding one re-breaks per-Customer deployment.

## Context

Next.js inlines all `NEXT_PUBLIC_*` environment variables into the JavaScript bundle at `next build` time. They are not read from the process environment at runtime. Setting them in the `environment:` block of a Docker Compose service definition has no effect — the value is `undefined` in the browser regardless of what the container sees at startup.

This caused the admin log viewer's SSE connection to silently never open: `NEXT_PUBLIC_API_URL` was `""` in the browser, the guard `if (!token || !apiUrl) return` exited early, and no `EventSource` was ever created. The symptom — "Connecting to log stream…" shown indefinitely — gave no indication that the variable was missing.

## Decision

Pass `NEXT_PUBLIC_*` variables to the frontend image as Docker build arguments (`ARG`) so they are available during `pnpm run build`.

In `frontend/Dockerfile`, the builder stage declares the argument and exports it as an environment variable before running the build:

```dockerfile
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm run build
```

In `deploy/docker-compose.prod.yml`, the `build.args` block passes the value from the host `.env` file into the image build:

```yaml
build:
  args:
    NEXT_PUBLIC_API_URL: https://${DOMAIN}
```

## Considered options

- **Runtime injection via a custom `server.js` wrapper** — rewrite `__NEXT_PUBLIC_*` placeholders in the built output at container startup. Avoids rebuilding per environment but requires a non-trivial wrapper script and diverges from the standard Next.js standalone output.
- **Hardcode the URL in source** — removes the build-arg indirection but breaks every other deployment.
- **Use server components only for API calls** — eliminates the need for `NEXT_PUBLIC_API_URL` entirely for server-side fetches. Already done for most data fetching via `src/lib/api.ts`. Only applicable where browser-side access (SSE, client fetch) is genuinely needed.

## Consequences

- The frontend image is environment-specific: a production image built for `openavisio.org` cannot be redeployed to a different domain without a rebuild. Acceptable for a self-hosted single-tenant deployment.
- Any new `NEXT_PUBLIC_*` variable must be added to both the `ARG`/`ENV` block in `Dockerfile` and the `build.args` block in `docker-compose.prod.yml`, or it will silently be `undefined` in the browser.
- `API_URL` (server-side only, no `NEXT_PUBLIC_` prefix) remains a runtime environment variable and does not require this treatment.
