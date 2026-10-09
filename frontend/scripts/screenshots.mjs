/**
 * Retake the app screenshots against a running instance.
 *
 *   node scripts/screenshots.mjs                        # every view, docs frame
 *   SHOT_VIEWS=overview,documents,conditions node …      # just the README's three
 *   SHOT_WIDTH=1400 SHOT_HEIGHT=1064 OUT_DIR=… node …    # the website's frame
 *
 * Deliberately NOT in e2e/: that is Playwright's testDir, and CI runs everything
 * in it. This drives the browser directly instead of being a test — it asserts
 * nothing, it just captures.
 *
 * Signs in as the demo ADMIN, because the existing set shows the Admin section
 * in the sidebar. Language comes from the NEXT_LOCALE cookie (i18n/request.ts),
 * dark mode from the emulated colour scheme: the theme is `system` + `enableSystem`
 * (app/layout.tsx), so prefers-color-scheme decides and nothing has to be clicked.
 */

import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const BASE_URL = process.env.BASE_URL ?? "https://demo.openavisio.org";
const EMAIL = process.env.SHOT_EMAIL ?? "caregiver@demo.openavisio.org";
const PASSWORD = process.env.SHOT_PASSWORD ?? "Demo123!Care";
const OUT = process.env.OUT_DIR ?? resolve(HERE, "../../docs/screenshots");
const PATIENT = process.env.SHOT_PATIENT ?? "Lena Hoffmann";
// The docs set is 1440x900; the website (openavisio.org) carries its own copies at
// 1400x1064. Same walk, different frame — hence the override rather than a second script.
const WIDTH = Number(process.env.SHOT_WIDTH ?? 1440);
const HEIGHT = Number(process.env.SHOT_HEIGHT ?? 900);

// name -> path suffix under /patients/<id>. "overview" is the patient landing page;
// "dashboard" is the section of that name, which is a different screen — the old set
// called the overview "dashboard" and had no shot of the real one.
const VIEWS = [
  { name: "overview", path: "" },
  { name: "dashboard", path: "/dashboard" },
  { name: "documents", path: "/documents" },
  { name: "medications", path: "/medications" },
  { name: "conditions", path: "/conditions" },
  { name: "measurements", path: "/measurements" },
  { name: "lab-results", path: "/lab-results" },
  { name: "expenses", path: "/expenses" },
  { name: "calendar", path: "/calendar" },
  // The calendar opens on the current month, so a shot of a fixed-date event has to
  // walk there. The demo's Widerspruch deadline sits on the Bescheid's own timeline
  // (ADR 041) rather than on a rolling date, so the target month is spelled out and
  // the walk is computed at capture time.
  // `open` puts the detail drawer on screen. It darkens the page behind it with a
  // bg-black/40, so this shot is dimmer than the others on the feature page. Kept
  // anyway: without it the frame shows an empty month and a truncated pill, and the
  // Kasse, the Aktenzeichen, the quoted reasoning and the derivation are the feature.
  { name: "deadline", path: "/calendar", month: "2026-06", open: "Widerspruchsfrist" },
  { name: "pflegegrad", path: "/einstufung" },
  { name: "emergency-plan", path: "/emergency-plan" },
  { name: "care-notes", path: "/care-notes" },
  { name: "handout", path: "/handout" },
];

// SHOT_VIEWS=overview,documents,conditions restricts the run — the README only
// carries three, the website's feature page wants all of them.
const WANTED = process.env.SHOT_VIEWS?.split(",").map((v) => v.trim()).filter(Boolean);
const SELECTED = WANTED ? VIEWS.filter((v) => WANTED.includes(v.name)) : VIEWS;
if (WANTED && SELECTED.length !== WANTED.length) {
  const known = VIEWS.map((v) => v.name).join(", ");
  throw new Error(`SHOT_VIEWS names an unknown view. Known: ${known}`);
}

const fileName = (view, locale, theme) =>
  `${view}${locale === "de" ? "-de" : ""}${theme === "dark" ? "-dark" : ""}.png`;


/** Click the calendar's month arrows until `target` ("YYYY-MM") is on screen. */
async function walkToMonth(page, target) {
  const [ty, tm] = target.split("-").map(Number);
  const now = new Date();
  const steps = (now.getFullYear() - ty) * 12 + (now.getMonth() + 1 - tm);
  const arrow = page.getByRole("button", { name: steps > 0 ? /previous|zurück/i : /next|weiter/i });
  for (let i = 0; i < Math.abs(steps); i++) await arrow.click();
  if (steps !== 0) await page.waitForLoadState("networkidle");
}

async function capture(browser, locale, theme) {
  const context = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    // scale 1 on purpose: the committed set is exactly 1440x900, and doubling it
    // would silently replace every file with one of a different size
    colorScheme: theme,
    locale: locale === "de" ? "de-DE" : "en-US",
  });
  const { hostname } = new URL(BASE_URL);
  await context.addCookies([
    { name: "NEXT_LOCALE", value: locale, domain: hostname, path: "/" },
  ]);

  const page = await context.newPage();
  await page.goto(`${BASE_URL}/login`);
  await page.locator('input[type="email"]').fill(EMAIL);
  await page.locator('input[type="password"]').fill(PASSWORD);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/patients$/, { timeout: 30_000 });

  await page.getByRole("link", { name: new RegExp(PATIENT) }).first().click();
  await page.waitForURL(/\/patients\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  const patientUrl = page.url();

  for (const view of SELECTED) {
    await page.goto(patientUrl + view.path);
    await page.waitForLoadState("networkidle");
    if (view.month) await walkToMonth(page, view.month);
    // A month grid shows a deadline as a truncated pill and says nothing about it.
    // Opening it is the shot worth having: Kasse, Aktenzeichen, the Kasse's own
    // wording, how the date was derived, and the two ways to close it.
    if (view.open) {
      await page.getByText(new RegExp(view.open)).last().click();
      await page.waitForTimeout(1200);
    }
    // Only the content area: the sidebar and the preview banner are chrome, and
    // they eat most of the frame. SidebarInset renders this <main>, it is capped
    // at viewport height (h-svh, overflow-hidden), so this stays a fixed-size
    // slice rather than the whole scrollable page.
    const main = page.locator('main[data-slot="sidebar-inset"]');
    await main.waitFor();
    const out = `${OUT}/${fileName(view.name, locale, theme)}`;
    await main.screenshot({ path: out });
    console.log(`  ${out.replace(`${OUT}/`, "")}`);
  }

  await context.close();
}

const browser = await chromium.launch();
await mkdir(OUT, { recursive: true });
console.log(`capturing ${BASE_URL} -> ${OUT}`);
for (const locale of ["en", "de"]) {
  for (const theme of ["light", "dark"]) {
    console.log(`${locale} / ${theme}`);
    await capture(browser, locale, theme);
  }
}
await browser.close();
console.log("done — review the diff before committing, the demo data changes over time");
