# A User can get back in: password reset, and a recovery code for when the mailbox is gone

**Status:** accepted (2026-07-26)

**Depends on:** ADR 014 (every User keeps a password beside their passkey)

There is no password reset in OpenAvisio. `auth.py` has login, invite acceptance
and passkeys, and nothing that recovers an account. SMTP credentials live in
`SystemSetting`, set by an admin through the UI, so a freshly provisioned
Deployment cannot send mail at all.

That was survivable while every Deployment was an organisation with several
admins: someone else could always let you back in. It is not survivable for a
household. A single User who forgets their password and loses the device holding
their passkey has lost their child's medical record, permanently, and there is
nobody else on the Deployment to ask.

A silent Deployment is the larger half of the problem. Without SMTP there are no
caregiver invitations, no appointment reminders, and no Widerspruch Deadline
warning — a feature whose entire purpose is warning someone in advance.

## The decision

**SMTP falls back to the environment.** `_get_smtp_config` reads `SystemSetting`
first, as now, and falls back to `SMTP_*` environment variables when no host is
configured there. A hosted Deployment gets working mail from the provisioning
template; a self-hoster configures it in the UI exactly as before and notices
nothing.

**A standard password reset**: request by email address, single-use token with a
short lifetime, response identical whether or not the address exists.

**A recovery code, shown once at setup.** Reset by mail assumes the mailbox is
still reachable, which is a bad assumption for an address someone has not
maintained in a decade. The code is the answer to that, and it is the only
recovery path that survives losing both the password and the mailbox.

**The operator gets no emergency access.** A hosted Deployment is set up by the
customer through the bootstrap token; nobody running the service has an account
on it. Keeping a way in would contradict what the AVV says, and a documented
recovery path that the customer controls is the honest version.

## Both new paths are potential MFA bypasses

Passkeys are already a second factor, and a stronger one than TOTP. When
passkey-only login becomes enforceable, **the reset flow and the recovery code
must not walk around it.** That constraint belongs in the endpoints from the
first commit: retrofitting it later means reworking the most sensitive route in
the application. This ADR is the reason a future MFA change is small.

## Consequences

**Good:**
- Self-service signup becomes possible at all; lockout stops being terminal
- A hosted Deployment can send mail from its first minute, so reminders and
  deadline warnings work as designed
- Mail configuration stays a customer's own choice on a self-hosted box

**Trade-offs:**
- The operator now runs a mail relay and inherits its deliverability problems
- A recovery code nobody wrote down is not a recovery path, and support cannot
  fix that. It is shown once, deliberately.
