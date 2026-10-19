# A mail speaks the household's language and names its occasion

**Status:** accepted (2026-10-18)

**Depends on:** ADR 046 (the household), #251 (no health data in mails)

Every notification mail was English, also on a German household, and without "Details in emails" each said only "There is something new in OpenAvisio, please log in". That reads like spam and gets ignored (#329).

## The decision

**A mail speaks the Deployment's default language**, German or English. The setup wizard sets it, the family page changes it. There is no per-person language: the language picker lives in the browser only.

**A mail without details names its occasion and nothing else**: a document is ready, an appointment tomorrow, a deadline ends in five days, you have access to a record. No patient, no title, no finding. The kind of occasion is not health data.

**The invitation says who invites and to what**, for example "Anna Riedel lädt dich zu OpenAvisio ein" and the household's name. Neither is health data, and an anonymous invitation looks like phishing.

**In a household, "added as a caregiver" is off by default.** A member gets access right after accepting the invitation, so the second mail says nothing new. Outside a household it stays on.

**The mail per processed document is off by default** and can be switched on with the other mails on the family page.

The switches stay per Deployment. A switch per person is its own issue if a family asks for it.

## Consequences

- A household that changes its language changes all future mails at once.
- Explicit switches always win over the household default.
