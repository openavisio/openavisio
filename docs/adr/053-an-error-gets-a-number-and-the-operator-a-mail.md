# An error gets a number, and the operator gets a mail

**Status:** accepted (2026-10-18)

**Depends on:** #115 (the document watchdog), #250 (`OPS_ALERT_EMAIL`)

Until now the operator heard of an error only through the watchdog, which covers failed documents, or through a customer who wrote in. A broken page or a failed save stayed in a log on the box that nobody reads.

## The decision

**Every unhandled backend error answers 500 with an `error_id`**, eight hex characters, and is logged under that id with its traceback. Then **one mail goes to `OPS_ALERT_EMAIL`**, at most one per hour per Deployment (Redis `ops:error-mail`). It holds the id, the host, the time, the route template and the exception's class. It never holds the exception's message or the request, because either may contain health data. Further errors in that hour are only in the log. If `OPS_ALERT_EMAIL` is unset, as on a self-hosted install by default, no mail goes out.

**The app's error page shows a number and offers a report.** The number is Next's digest. The frontend log has it next to the backend's error text, which carries the `error_id`. On a hosted Deployment, "Fehler melden" opens a prepared mail to info@openavisio.app with the number and the page. A self-hosted install shows the number only.

Error tracking (GlitchTip, Sentry) was considered and left out: it is another service, and its reports would need scrubbing of health data first.

## Consequences

- A burst of errors is one mail; the log tells how many.
- Errors that never reach the backend (a broken client component) are seen only through a customer's report.
