# ADR 006: Next.js 16 middleware via proxy.ts + Auth.js v5 session management

**Status:** Accepted

## Context

The frontend needs per-request auth guards (redirect unauthenticated users to `/login`) and a setup check (redirect to `/setup` if the org is not initialised). Two subtle issues shaped the implementation.

### Middleware filename

Next.js conventionally loads `src/middleware.ts` as the Edge middleware entry point. In Next.js 16 with Turbopack, **any file in `src/` that exports a `config.matcher` is compiled and registered as middleware**, regardless of filename. The file was named `proxy.ts` from an earlier iteration and continues to work correctly — renaming it would be a purely cosmetic refactor.

### Auth.js v5 cookie naming

The original middleware used `getToken()` from `next-auth/jwt` (the Auth.js v4 API). Auth.js v5 renamed the session cookie from `next-auth.session-token` to `__Secure-authjs.session-token`. `getToken()` looked up the old name and always returned `null`, causing every authenticated request to be redirected back to `/login` immediately after a successful sign-in — a tight redirect loop.

**Fix:** replaced `getToken()` with the `auth()` wrapper exported by `@/auth`. When used as `auth(handler)`, it reads the correct v5 cookie and populates `req.auth` with the decoded session.

### Token refresh

The backend issues access tokens with a 15-minute TTL. Without refresh logic, users would receive silent 401s from API calls after 15 minutes despite having a valid Auth.js session (which lives 30 days).

**Fix:** the `jwt` callback in `auth.ts` now:
1. Stores `expiresAt` from the initial login response
2. On every subsequent callback invocation, checks expiry with a 30-second buffer
3. If the access token is about to expire, calls `POST /api/auth/refresh` silently
4. On refresh failure, sets `token.error = "RefreshTokenExpired"`

The middleware checks `req.auth?.error === "RefreshTokenExpired"` and redirects to `/login?error=SessionExpired`, which shows a localised banner.

## Rejected alternatives

**Rename `proxy.ts` → `middleware.ts`.** Would work identically; deferred as the current name causes no issues and the rename has no functional benefit.

**Keep `getToken()` with explicit `salt` / `cookieName` parameters.** Auth.js v5 encrypts session tokens as JWE using the cookie name as the salt; `getToken()` can be made to work with the correct parameters, but the `auth()` wrapper is the idiomatic v5 approach and requires no manual configuration.
