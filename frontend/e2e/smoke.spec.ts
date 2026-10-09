import { test, expect, type Page } from "@playwright/test";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

// The bug class this suite exists for (hydration mismatch, a theme script eating
// React's meta tags) renders a dead page while every HTTP status stays 200. It is
// only ever visible in the console. So: any console error fails the test.
function failOnConsoleErrors(page: Page) {
  const errors: string[] = [];
  // echoed as they happen, not just asserted at the end: when the test dies on a
  // timeout instead, the assertion never runs and the console is all you have.
  const record = (text: string) => {
    console.log(`[browser] ${text}`);
    errors.push(text);
  };
  page.on("console", (msg) => msg.type() === "error" && record(msg.text()));
  page.on("pageerror", (err) => record(String(err)));
  return errors;
}

test("login, open a patient, and keep navigating", async ({ page, request }) => {
  // dev-only endpoint: admin@openavisio.dev + a Demo Patient with an explicit
  // grant (the admin *role* confers no clinical access — ADR 025).
  await request.post(`${BACKEND}/api/dev/seed`);
  const errors = failOnConsoleErrors(page);

  await page.goto("/login");
  await page.locator('input[type="email"]').fill("admin@openavisio.dev");
  await page.locator('input[type="password"]').fill("Admin123!Admin");
  await page.locator('button[type="submit"]').click();

  await expect(page).toHaveURL(/\/patients$/);
  await page.getByRole("link", { name: /Demo Patient/ }).click();
  await expect(page.getByRole("heading", { name: "Demo Patient" })).toBeVisible();

  // Handout (ADR 048), reached from the patient page.
  await page.locator('a[href$="/handout"]').first().click();
  await page.waitForURL(/\/handout$/);
  await expect(page.getByRole("button", { name: /PDF herunterladen|Download PDF/ }))
    .toBeVisible({ timeout: 15_000 });
  await page.goBack();

  // The calendar page mounts CalendarFeedPanel, which fetches on mount (#192) —
  // a broken feed action would only ever surface here, via failOnConsoleErrors.
  await page.locator('a[href$="/calendar"]').first().click();
  await expect(page.getByRole("heading", { name: /Kalender abonnieren|Subscribe to calendar/ })).toBeVisible();
  await page.goBack();

  // Expenses tab (#218) — a new patient section (ADR 033: keep the walk in sync).
  // The Add button is always present; asserting on it proves the page mounted clean.
  // Wait for the navigation itself before asserting: this page is server-rendered
  // behind three API calls, and on a cold CI box it needed longer than the default
  // 5s expect timeout — the button was never missing, the page was still coming.
  await page.locator('a[href$="/expenses"]').first().click();
  await page.waitForURL(/\/expenses$/);
  await expect(page.getByRole("button", { name: /Ausgabe hinzufügen|Add expense/ }))
    .toBeVisible({ timeout: 15_000 });
  await page.goBack();

  // Einstufung tab (ADR 042) — the ninth patient section, same rule as Expenses
  // above. The Demo Patient has no Einstufung, so the empty state is what proves
  // the page rendered rather than 500'd: it is a server component behind two API
  // calls, and an empty list is the state a fresh install is actually in.
  await page.locator('a[href$="/einstufung"]').first().click();
  await page.waitForURL(/\/einstufung$/);
  await expect(page.getByRole("button", { name: /Einstufung hinzufügen|Add Einstufung/ }))
    .toBeVisible({ timeout: 15_000 });
  await page.goBack();

  // Emergency Plan tab (ADR 048), same rule. The Demo Patient has none, so the
  // create button is what proves the page rendered behind its three API calls.
  await page.locator('a[href$="/emergency-plan"]').first().click();
  await page.waitForURL(/\/emergency-plan$/);
  await expect(page.getByRole("button", { name: /Notfallplan anlegen|Create emergency plan/ }))
    .toBeVisible({ timeout: 15_000 });
  await page.goBack();

  // Care Notes tab (ADR 048), same rule as the Emergency Plan above.
  await page.locator('a[href$="/care-notes"]').first().click();
  await page.waitForURL(/\/care-notes$/);
  await expect(page.getByRole("button", { name: /Alltagsinfos anlegen|Create care notes/ }))
    .toBeVisible({ timeout: 15_000 });
  await page.goBack();

  // Carer Updates tab (ADR 049), same rule.
  await page.locator('a[href$="/carer-updates"]').first().click();
  await page.waitForURL(/\/carer-updates$/);
  await expect(page.getByRole("button", { name: /Rückmeldung hinzufügen|Add carer update/ }))
    .toBeVisible({ timeout: 15_000 });
  await page.goBack();

  // Intake Forms (ADR 047): its own upload route, then the sheet page. CI runs no
  // worker, so the form stays in "reading"; that state rendering is the assertion.
  await page.locator('a[href$="/intake-forms"]').first().click();
  await page.waitForURL(/\/intake-forms$/);
  await page.getByRole("button", { name: /Anamnesebogen hochladen|Upload intake form/ }).click();
  await page.locator('input[name="file"]').setInputFiles({
    name: "intake.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 intake form"),
  });
  await page.locator('form button[type="submit"]').click();
  await page.waitForURL(/\/intake-forms\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  await expect(page.getByText(/wird gelesen und aus der Akte|being read and answered/)).toBeVisible();
  await page.goBack();
  await page.goBack();

  // The chat, all the way through (#201). Opening the overlay proves nothing:
  // the payload sent to the aiservice was rejected for months and the user only
  // ever saw "AI service unavailable". So: ask, and read the answer.
  await page.getByRole("button", { name: /AI Chat|KI-Chat/ }).click();
  await expect(page).toHaveURL(/chat=1/);
  await page.getByRole("textbox").fill("Wann war der letzte Termin?");
  await page.getByRole("button", { name: /Send|Senden/ }).click();
  // wait for whichever lands, so a failure names itself: asserting only on the
  // disclaimer turned a backend 500 into a bare "element not found" after 30s.
  await expect(page.locator('[data-testid="chat-disclaimer"], [data-testid="chat-error"]'))
    .toBeVisible({ timeout: 30_000 });
  await expect(page.locator('[data-testid="chat-error"]')).toHaveCount(0);
  await expect(page.locator('[data-testid="chat-disclaimer"]')).toBeVisible();
  await page.getByRole("button", { name: /Close|Schließen/ }).click();
  await expect(page).not.toHaveURL(/chat=1/);

  // The second click is the actual test: a <div> in a <ul>, a stray loading.tsx —
  // each of those broke *this* click while the first one still worked.
  await page.locator('a[href="/settings"]').first().click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

  expect(errors).toEqual([]);
});

// ADR 044: the recovery page is the only way back in for a household with one
// login. It is public, it is reachable from the login form, and a wrong code
// must say so rather than blank the page. Nobody would notice it rotting
// otherwise — it is used once, years after setup.
test("the recovery page loads and refuses a wrong code", async ({ page }) => {
  const errors = failOnConsoleErrors(page);

  await page.goto("/login");
  await page.getByRole("link", { name: /Passwort und Passkey verloren|Lost your password/ }).click();
  await expect(page).toHaveURL(/\/recover$/);

  await page.locator('input[type="email"]').fill("nobody@openavisio.dev");
  await page.locator('input[type="text"]').fill("AAAAA-BBBBB-CCCCC-DDDDD");
  await page.locator('input[type="password"]').fill("Whatever9!");
  await page.locator('button[type="submit"]').click();

  await expect(page.getByText(/stimmen nicht|is wrong/)).toBeVisible({ timeout: 15_000 });

  // The rejection is the point of this test, and the browser logs every failed
  // request to the console — so the one 400 we asked for is not a page error.
  // Everything else still fails the test.
  expect(errors.filter((e) => !/status of 400/.test(e))).toEqual([]);
});

// #264: the welcome mail links to /setup#token=…. The token must land in the
// field, leave the address bar, and never be stored anywhere the browser keeps.
test("the setup wizard takes the bootstrap token from the fragment", async ({ page, context }) => {
  const errors = failOnConsoleErrors(page);

  // not hex: a random cookie value (the CSRF token) once contained "abc"
  await page.goto("/setup#token=qxz-setup");
  await expect(page).toHaveURL(/\/setup$/);

  // Language, organisation and SMTP need nothing filled in; step 4 has the field.
  for (let i = 0; i < 3; i++) await page.getByRole("button", { name: /^(Next|Weiter)$/ }).click();
  await expect(page.locator('input[type="password"]').first()).toHaveValue("qxz-setup");

  const stored = await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }));
  expect(stored).not.toContain("qxz-setup");
  expect(JSON.stringify(await context.cookies())).not.toContain("qxz-setup");

  expect(errors).toEqual([]);
});
