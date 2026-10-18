# A household has one Household Manager, and the word "admin" is not shown to it

**Status:** accepted (2026-10-18)

**Depends on:** ADR 025 (admin role has no clinical access), ADR 046 (household Deployment), avisiohub ADR 0007 (hosted Deployments)

**Resolves** #334. Grilled with the maintainer on 18 Oct 2026.

The person who sets up a household Deployment gets `role=admin`. In a household, ADR 046 hid user management. On a hosted Deployment, #324 then cut the admin menu down to Invitations and Audit. That was meant to keep the operator's pages (AI, system, logs, licence, data governance) away from the customer, but the cut also took the household's own pages with it. Nothing records a reason for hiding members and the organisation settings. Today the first person of a household cannot remove the other parent, take back an invitation, rename the record, choose which mails arrive, or export a child's data (`GET /patients/{id}/export/fhir` exists, but nothing calls it). They also see a menu called "Administration" with two entries, which reads as "you are not in charge here".

## The decision

**The person who sets up a household is its Household Manager.** The role stays `admin` in code. The UI never says "admin" or "administrator" in a household. It shows only what the Household Manager can do.

**One menu entry, "Familie", for the Household Manager only.** It holds:

- the members, each with "Entfernen". This deactivates the login and revokes every PatientAccess grant the member holds. Their entries stay, under their name. Erasure stays self-service (ADR 025, Erasure).
- invitations, sent and **revocable**. Invitees always join as `user`.
- the record's name and language
- which mails the household receives (the existing notification settings)
- the audit log
- "Verwaltung übertragen": the Household Manager hands the role to another member and becomes an ordinary member. There is always exactly one Household Manager.

Not on the page: the Impressum fields, which belong to the operator on a hosted Deployment, and the household/organisation switch.

**Export per Patient, for everyone who can view that Patient:** one ZIP holding the FHIR bundle and every Document as its file. After a cancellation, this is what the family takes with it.

**The "Vertrag" card in the settings (hosted only) shows to the Household Manager only.** Cancelling needs the ordering mail address at Stripe anyway.

**When the Household Manager is gone for good** (death, permanently unreachable), the operator transfers the role on request, once the contract holder is proven. The operator gets a small command for this. It changes the role and touches no data.

**This applies to every household, hosted or self-hosted.** A self-hosted household also sees the operator pages, because it is its own operator. On a hosted Deployment those stay locked (`operator_only`, #324).

## Consequences

- One Household Manager is a single point of failure. The transfer and the operator command are the answer; a second manager was considered and rejected.
- The member and organisation endpoints already answer an admin on hosted. The work is mostly UI, a revoke endpoint for invitations, the transfer, and the ZIP export.
- The privacy page's promise of an export becomes true.
