# ADR 013 — i18n Locale Resolution Strategy

**Date:** 2026-06-04
**Status:** Accepted

## Context

OpenAvisio uses `next-intl` for internationalisation. We need a clear, predictable rule for which language a user sees.

Complicating factors:
- `next-intl` v3 with `localePrefix: "never"` — locale is not in the URL, so next-intl's middleware cannot detect it from the path.
- `proxy.ts` is a custom Auth.js v5 middleware that runs before next-intl. It must explicitly chain to next-intl's `createMiddleware`; otherwise `requestLocale` in `getRequestConfig` is always `undefined`.
- Each OpenAvisio deployment is a single-org installation. The org chooses a language during setup (the "system language"). Users should inherit this default until they set their own preference.

## Decision

**Locale resolution priority (highest wins):**

1. `NEXT_LOCALE` cookie — set when the user explicitly picks a language in Settings. Carried through every request by next-intl's middleware, surfaced as `requestLocale` in `getRequestConfig`.
2. **Org default language** — fetched server-side from `GET /api/organization/status` (cached 1 h). Set during the setup wizard and stored on the `Organization` row as `default_language`.
3. `routing.defaultLocale` ("en") — hard fallback if the backend is unreachable.

`Accept-Language` detection was intentionally removed. In a clinical single-org deployment the org's configured language is a more reliable default than the browser's OS locale, which varies per device and is often wrong.

**"System" option in user settings:**

The Language picker in `/settings` includes a "System" button as the first option. Selecting it deletes the `NEXT_LOCALE` cookie (`max-age=0`), so the request falls back to the org default without any explicit user override. The settings page detects whether the current locale is system-derived by checking whether the cookie is absent.

## Middleware chain

```
Request
  → proxy.ts (Auth.js v5 token check)
      → createIntlMiddleware(routing)(req)   // sets x-next-intl-locale header from cookie
          → app RSC / getRequestConfig       // reads requestLocale from header
```

`proxy.ts` must call `handleIntl(req)` and return its response (not `NextResponse.next()`), otherwise the intl header is never set and every user always gets the org default (since `requestLocale` would always be undefined).

## Consequences

- Language changes are instant (cookie, no round-trip to backend).
- New users automatically see the org's language with no configuration required.
- The org `default_language` is a single row; changing it via the admin panel (future) would affect all "System" users on next page load (after the 1 h cache expires).
- No per-user `preferred_language` column in the DB — the cookie is the source of truth for explicit preferences.
