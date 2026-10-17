# OpenAvisio is a PWA, there is no mobile app

**Supersedes** ADR 023 (Capacitor shell), ADR 035 (Capacitor 7 for F-Droid) and ADR 036 (Google Play beside F-Droid). Decided by the maintainer on 17 Oct 2026.

ADR 023 built a Capacitor shell for store presence, a biometric app lock and a field for the Deployment URL. By October the shell was unmaintained: its CI job had been red since beta9, F-Droid carried a frozen `0.1.0-beta` from July (withdrawn the same day, fdroiddata !52974), and the version, signing and store paperwork cost time that went into nothing a family used.

## The decision

**OpenAvisio ships as a PWA only.** `mobile/`, its CI job and the app's own `PRIVACY.md` are deleted (git history keeps them), and the register page no longer offers an `openavisio://` link into an app that does not exist.

What the shell did is covered without it:

- **Getting there.** A family reaches its Deployment through the QR code and the home-screen icon of the installed PWA (avisiohub ADR 0010). Each Deployment is its own origin with its own icon, so no URL field is needed.
- **Biometrics.** Passkeys sign in with fingerprint or face.
- **Push**, when it comes, is Web Push, which an installed PWA gets on Android and iOS.

ADR 030 (touch-first mobile UX) stands; it applies to the PWA in a phone's browser.

## Consequences

- No store listing as a trust signal. The PWA has to be installed through the browser ("Zum Home-Bildschirm" on iOS); the welcome mail says how (avisiohub `docs/welcome-mail.de.md`).
- iOS may evict a PWA's local storage after long disuse. The records live on the server, so the cost is a sign-in, not data.
- Coming back to the stores is a new decision, starting from `mobile/` in git history, Capacitor 8, and `UpdateCheckMode: Tags` on F-Droid.
