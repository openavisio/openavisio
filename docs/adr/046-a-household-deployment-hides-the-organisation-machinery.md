# A household Deployment hides the organisation machinery, and one field says so

**Status:** accepted (2026-08-27)

**Depends on:** ADR 025 (admin role has no clinical access), ADR 043 (the License
file carries the limits)

`CONTEXT.md` has always admitted that an Organization can be "a care home, a
clinic, a household, or an individual". The software only ever believed the first
two. A parent who sets up a Deployment for one child is asked for an organisation
name before they have seen the product, and then handed eleven admin pages, of
which Groups, Sharing Purposes and user management describe a situation that will
never occur in their house.

This matters now because the household is the Customer we are about to approach
one by one, rather than through an association.

## The decision

**One boolean on the Organization, `is_household`, chosen in setup step 2 and
changeable later** in the organisation settings. Existing Deployments default to
false and change in no way.

When it is set:

- Groups, Sharing Purposes and user management disappear from the navigation
- the wizard stops asking for an organisation name and sets one silently
- the SMTP step is skipped when the environment already answers it (ADR 044)

**It is presentation only.** The endpoints behind those pages stay reachable and
stay guarded by the role and PatientAccess checks that already guard them. The
mode is not a permission layer: the only person who could call them is the admin
they belong to, and the switch sits in that same admin's settings.

**The vocabulary does not fork.** "Organisation" is not renamed to "Haushalt" in
household mode. Every string would exist twice, in two languages, forever, to
soften a word that appears on four screens.

## Why not derive it from the data

Counting the rows is free and needs no column: one User and no Groups is a
household by observation. It also deadlocks. The page you need in order to create
the second User is the page that is hidden while there is only one, and a menu
that rearranges itself when a grandmother accepts an invitation is a menu nobody
can be taught.

## Why not reorganise the menu instead

Moving the household-relevant admin pages (License, data governance, organisation,
AI backend) into `/settings` and leaving `/admin` for the multi-user pages would
need no flag at all. It is the better end state and a much larger edit, and it
still leaves the wizard asking a father for the name of his organisation.

## Consequences

**Good:**
- The first screen a private Customer sees stops describing a care home
- One column, one wizard question, no migration for anybody who does not want it
- A Selbsthilfegruppe that grows out of it flips one switch, it does not migrate

**Trade-offs:**
- A flag that changes what is visible will eventually be blamed for a missing
  menu entry. The switch is in plain sight in the settings for that reason.
- Two navigation states to keep working, and the smoke test walks only one of them
