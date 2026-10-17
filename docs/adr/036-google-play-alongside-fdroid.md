# ADR 036: The mobile app ships to Google Play alongside F-Droid

**Status:** Accepted (2026-07-19) · **Superseded by ADR 051** (2026-10-17): PWA only, no mobile app.

**Amended 2026-10-17: F-Droid is withdrawn.** The app sat on f-droid.org at `0.1.0-beta`
from July with `UpdateCheckMode: Static`, so every install stayed on that build, while the
app itself went unmaintained (the APK build has been red since beta9). A visibly stale beta
next to medical records does more harm than no listing, and paying families reach their
Deployment through the QR code and home-screen icon (avisiohub ADR 0010), not F-Droid. The
listing is disabled at our request in fdroiddata and `docs/fdroid/` is gone (the recipe stays
in git history). Play stays as decided below. Back on F-Droid when the app is maintained again,
then with `UpdateCheckMode: Tags`: since tags are plain SemVer (`docs/releasing.md`) every
release would reach it without a hand-made MR.

## Context

The mobile app is a thin Capacitor-7 shell (ADR 023, ADR 035) already published to
F-Droid. We want it on the Google Play Store too, for reach beyond F-Droid users.
Play imposes constraints F-Droid does not: a different signing model, mandatory
compliance forms, and, for new personal developer accounts, a closed-testing gate.

## Decision

**Publish the same `org.openavisio.app` to Play as a second channel.** Specific choices:

- **Signing / identity.** Keep one `appId`. F-Droid signs with its own key; Play uses
  Play App Signing (Google holds the app key, we hold only the upload key). The two
  channels therefore carry **different signatures**: a device can hold only one, and
  switching F-Droid to Play requires uninstall then reinstall. Acceptable, the shell's only
  local state is the Deployment URL + lock preference, so reinstall costs the user
  seconds. We do **not** chase F-Droid reproducible builds to unify the key.
- **Release pipeline.** Manual local `bundleRelease` (AAB), upload key kept out of the
  repo like the existing keystore (#59), uploaded by hand via the Play Console. No
  signing material in CI. Automate later only if release frequency ever demands it.
- **Review posture.** Submit as-is. The shell's native function (connect flow,
  biometric app-lock, `openavisio://` deep links) is the answer to Play's
  minimum-functionality / webview-wrapper policy. Fill Play's Health-app declaration
  honestly; the store listing describes a *client for a self-hosted server* and makes
  no medical/diagnostic claims. React to concrete rejections rather than pre-building
  against hypothetical ones.
- **Developer account.** Start on Martin Riedel's **personal** Play account (no legal
  entity exists yet). Migrate to an organisation account via Play's transfer once an
  entity exists, do not block the launch on a D-U-N-S number.
- **Privacy / data safety.** A `PRIVACY.md` in the repo is the required privacy policy.
  The Play link is a public URL, `openavisio.org/privacy` (preferred) or the Codeberg
  mirror, never the private Forgejo host. Data-safety form: **no data collected**, the
  shell sends nothing to the developer; Deployment URL and lock preference are stored
  locally only.
- **Release track.** Personal accounts must run **Closed Testing (~12 testers, 14 days)**
  before applying for production (Google gate, verify exact thresholds in the Console
  before starting). Path: Internal Testing now (verify signing/upload/deep-links/lock)
  → Closed Testing in parallel, testers sourced from the care / dup15q community →
  apply for production. F-Droid stays the primary channel meanwhile, so the gate blocks
  nothing.
- **Capacitor version.** Unchanged: Play builds the same Cap-7 source (ADR 035). No
  divergence, Play has no F-Droid Node constraint, but one codebase is simpler.

## Consequences

- `versionCode`: both stores build from the same tag → same versionCode, harmless
  because keys and tracks are independent. A Play-only rebuild needs a bumped
  versionCode Play has not seen.
- Two install bases that cannot cross-update; the store listings must not imply
  otherwise.
- The upload key is a second piece of signing material to back up and guard, alongside
  the F-Droid-independent keystore.
