# ADR 023: Mobile app via Capacitor shell around the web app, not a native rebuild

**Status:** Accepted

## Context

Store presence (Google Play, F-Droid, Apple App Store; iOS shortly after Android) is required for commercial credibility — not missing functionality: the existing Next.js frontend is already mobile-responsive, camera upload works via the browser, and web push covers reminders.

OpenAvisio is sold as one Deployment per customer (ADR 024) (separate LXC containers, arbitrary sub- or customer domains). That rules out a TWA: its trusted origins are baked into the app binary via `assetlinks.json` (no wildcards), so every new customer Deployment would require an app update.

A native rebuild in the Termix style (Expo/React Native) would mean a second complete UI codebase — every feature (documents, incidents, measurements, calendar, AI chat, sharing) built and maintained twice, by a solo maintainer.

## Decision

One **Capacitor shell** for Android and iOS wrapping the existing web frontend, with a configurable Deployment URL (Nextcloud/Immich model). Native extras (biometrics, camera integration, push) live in the shell — also needed to pass Apple's guideline 4.2 ("repackaged website") review.

Rollout: PWA manifest first (prerequisite, useful on its own) → Android (Google Play + F-Droid) → iOS shortly after. Push notifications are explicitly out of v1 — email reminders already exist and reach everyone.

Store identity: app name **OpenAvisio**, package ID **`org.openavisio.app`** (irreversible once published), published under an Individual developer account ("Martin Riedel" as seller — sole proprietors cannot use Apple's Organization enrollment), converted to an organization account once a legal entity exists. Shell code lives in `mobile/` in the monorepo. The Feb 2026 native experiments (openavisio-mobile-android/-ios, openavisio-sdk-kotlin/-swift) are archived, superseded by this ADR.

## Consequences

**Good:**
- One UI codebase; every future web feature ships to the stores for free
- One shell serves both platforms and any number of customer Deployments — no app update when a customer Deployment is added

**Trade-offs:**
- F-Droid forbids proprietary push (no FCM) — push must use Web Push/UnifiedPush
- The shell needs a Deployment-connection flow — decided: invite link/QR configures the Deployment (building on the existing invite tokens, ADR 011), with manual URL entry as fallback for self-hosters
- WebAuthn does not work inside WebViews — in-app login is email+password; the shell adds a biometric app lock (Face ID/fingerprint guarding the stored session) instead. Passkeys stay a browser feature; a native passkey bridge (needs associated-domain files per Deployment domain) only if customers ask
- Apple review for a medical-data app remains a risk; developer account 99 €/yr
