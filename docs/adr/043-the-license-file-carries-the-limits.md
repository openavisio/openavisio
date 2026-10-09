# The license file carries the limits, the code no longer decides them

**Status:** accepted (2026-07-26)

**Amends:** `docs/license-format.md` (format version 1 → 2)

Today a Tier is a switch with two positions. `license.py` hardcodes
`PERSONAL_PATIENT_LIMIT = 10` and `PERSONAL_USER_LIMIT = 3`, and Commercial means
unlimited. A `.lic` file carries `tier` and no numbers at all.

That worked while there were two kinds of Deployment: a homelab and a paying
organisation. It stops working the moment there are sizes in between — a single
household, a Selbsthilfegruppe of thirty families, a care service with eighty
Patients. Each of those needs a different pair of numbers, and none of them is a
new Tier.

## The decision

**License format version 2 adds `max_patients` and `max_users`.** Both are
integers. The signature already covers every field except `sig` through canonical
JSON, so no new mechanism is involved and no key changes.

**`license.py` reads the numbers from the file** instead of deriving them from
the Tier. `Tier` stays as it is: `personal` without a file, `commercial` with one.
It describes which terms apply, not how big the Deployment may be.

**The Personal defaults are unchanged: 10 Patients, 3 Users.** They are the
numbers a self-hoster gets with no file present, and shrinking them would only
punish the audience that ADR 034 exists to reach. A self-hoster who runs into a
limit does not become a customer, he uninstalls.

**Version 1 files keep working.** A file without the new fields falls back to
unlimited, which is what `commercial` meant when it was issued.

## Why not an environment variable

Setting the limits per box through the environment would be free and needs no
format change. It is also unsigned, which makes it a suggestion rather than an
entitlement, and it would leave two ways to answer the same question. The
license file already exists to answer exactly this one.

## Consequences

**Good:**
- Any number of plan sizes without a code change or a new Tier
- Nothing has to be reported back from a Deployment for billing to work — the
  file states what was bought, the Deployment enforces it, and no usage
  telemetry ever leaves a box holding health data
- Upgrading a customer is a new file, not a redeploy

**Trade-offs:**
- A second format version to keep readable, forever
- Growth is only visible when a customer says so. Deliberate: the alternative is
  counting Patients on someone else's server and sending the number home.
