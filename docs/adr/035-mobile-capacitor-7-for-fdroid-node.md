# ADR 035: The mobile app stays on Capacitor 7 until F-Droid's Node catches up

**Status:** Accepted (2026-07-19)

## Context

The mobile app is a Capacitor shell (ADR 023) published to F-Droid (#60). F-Droid
builds every app from source **on its own buildserver**, which is `debian/trixie64`
with apt sources limited to `trixie` + `-updates` / `-backports` / `-security` — no
`sid`, no `unstable` (see fdroidserver `buildserver/provision-apt-get-install`).

Debian trixie ships **Node 20**; trixie-backports has no newer node. Pulling Node
from NodeSource is possible but discouraged — exactly one app in all of fdroiddata
does it, and the reviewer asked us not to.

`@capacitor/cli` 8 hard-requires **Node ≥ 22** (`engines.node`), which the
buildserver cannot provide from Debian. `@capacitor/cli` 7 requires only Node ≥ 20.

## Decision

**Pin the mobile app to Capacitor 7** (all `@capacitor/*` on `^7`, and
`@aparajita/capacitor-biometric-auth` on `9.1.2`, its Capacitor-7 line). This lets
F-Droid build the app with stock Debian Node, no third-party apt repo.

Do **not** bump to Capacitor 8+ until F-Droid's buildserver ships Node ≥ 22 from
Debian.

## Consequences

**Good:**
- The F-Droid build uses `apt-get install nodejs npm` — nothing external.
- No behaviour change: the biometric plugin 9.1.2 exposes the same
  `checkBiometry` / `authenticate` API `shell.js` already uses; the shell is
  otherwise a thin WebView.

**Trade-offs:**
- We track one Capacitor major behind latest. For a shell that only loads a remote
  URL and gates launch with biometrics, that costs nothing today.
- The pin is invisible in `package.json` (JSON has no comments) — hence this ADR.
  A Capacitor bump is a deliberate, F-Droid-gated decision, not a routine update.

**Upgrade path:** when Debian stable (or the F-Droid buildserver) provides Node ≥ 22,
bump Capacitor and the biometric plugin together, drop this constraint, and switch
the fdroiddata recipe's Node source back if needed.
