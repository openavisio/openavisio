# ADR 014: Passkey authentication alongside passwords

**Status:** Accepted

## Context

Users currently authenticate with email and password only. Passkeys (WebAuthn discoverable credentials) provide a phishing-resistant sign-in path that is faster and more secure for day-to-day use. The goal is to add passkeys as an alternative — not a replacement — for password authentication, since not all devices support platform authenticators and some Users may prefer or need a fallback.

## Decisions

### Passkeys alongside passwords

Passkeys are an additional sign-in method. Every User still has a password (set during invitation acceptance). This ensures no User is locked out if they lose their device or sign in from a shared machine.

### Post-login registration only

Users register passkeys from their profile settings page, after signing in with a password. The invitation/registration flow is unchanged.

### Multiple passkeys per user

A User may register any number of passkeys. Each credential is stored as a row in a new `passkey_credentials` table keyed to the User, with a user-defined label, public key, credential ID, sign count, and AAGUID. Users can add, rename, and delete individual passkeys from their profile settings.

### Usernameless (discoverable) flow on login

The sign-in challenge is sent with no `allowCredentials` — the browser presents all passkeys registered for this origin. Passkeys must be created with `residentKey: required` and `userVerification: required`. The backend identifies the User from the `credentialId` returned in the assertion response.

### Challenge storage via signed cookie

The server-generated WebAuthn challenge is stored in a short-lived `HttpOnly` cookie signed with `app_secret`. On assertion or attestation verification, the challenge is read from the cookie, verified, and the cookie is cleared in the response. The cookie TTL is 5 minutes. This is stateless — no extra table or cleanup job.

### Auth.js integration via new credentials provider

A second `CredentialsProvider("passkey", ...)` is added to `auth.ts`. It calls `POST /api/auth/passkey/authenticate` on the FastAPI backend, which verifies the WebAuthn assertion and returns the same `{ access_token, refresh_token, expires_at, email, role }` shape as password login. The JWT callback and session shape are unchanged.

### Libraries

- Frontend: `@simplewebauthn/browser` — handles the browser WebAuthn ceremony
- Backend: `py_webauthn` (Duo Security / 1Password) — server-side registration and authentication verification

## Rejected alternatives

**Passkeys replacing passwords.** Device loss or shared-machine sign-in would leave Users with no recovery path.

**Auth.js v5 built-in WebAuthn provider.** Requires a database adapter; the current setup uses a JWT-only Auth.js strategy with no DB adapter. Adopting it would require significant refactoring for no benefit beyond a new credentials provider.

**One-time bridge token.** FastAPI verifies the assertion and returns a short-lived token that the existing credentials provider accepts. More moving parts than a dedicated provider with no compensating benefit.

**Email-first passkey flow.** User types email, server sends matching `allowCredentials`. Rejected in favour of the simpler usernameless UX that modern passkey implementations expect.

**Challenge stored in database.** A `webauthn_challenges` table with TTL cleanup is viable but adds schema migration and write load for a flow entirely covered by a signed stateless cookie.
