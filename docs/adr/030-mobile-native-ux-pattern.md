# ADR 030: Mobile UX — bottom tab bar, touch-first sizing, native chrome

**Status:** Accepted

## Context

The UI was built desktop-first: a hamburger → drawer sidebar (a web pattern, not a
native one) and desktop-sized touch targets throughout (icon buttons at `p-1`,
toggles at `py-1`, dense list rows). On a phone — and especially inside the
Capacitor app (ADR 023) — buttons are too small to hit reliably and the app reads
as a mobile *website*, not a native app.

## Decision

Adopt a touch-first mobile pattern; build the foundation before per-screen polish.

**1. Bottom tab bar (primary mobile navigation).** On phones, a fixed bottom tab bar
holds the few most-used destinations (thumb-reachable), with a "More" tab opening the
existing drawer for everything secondary (Groups, Data sharing, Admin, Settings). The
sidebar becomes desktop-only. This is the native iOS/Android pattern and the biggest
native-feel lever.

**2. Touch-first sizing (global).** Interactive elements meet the platform minimum —
**44×44px (iOS HIG) / 48dp (Material)** — enforced centrally via the Button/Input/
icon-button component sizes and list-row heights, so it holds everywhere, not screen
by screen. Larger sheets/dialogs; no hover-only affordances (a phone has no hover).

**3. Native chrome.** `viewport-fit=cover` + `env(safe-area-inset-*)` padding so the
header and bottom bar clear the notch and home indicator. Momentum scrolling, no
horizontal body scroll, tap highlight tuned.

**4. Foundation first, then screens.** Ship the foundation (safe-area, sizing tokens,
bottom nav) as one layer, then feature-polish the top screens (documents, lab results,
patient, verify) on top. Desktop layout is unchanged — everything is behind the mobile
breakpoint.

## Consequences

- One place raises touch targets app-wide; per-screen work becomes polish, not rescue.
- The mobile information architecture gets a real home (bottom tabs + More drawer)
  instead of a hidden hamburger.
- The Capacitor shell finally feels like an app: safe areas, thumb navigation, tappable
  controls.
- Desktop is untouched (mobile breakpoint only); risk is contained to small screens.
- Follow-ups: gesture/back-button handling, native transitions, and the per-screen
  polish tracked in the mobile-overhaul issue.
