# ADR 032 — The public release is a fresh snapshot, not this history

**Status:** accepted (2026-07-14)

## Context

OpenAvisio is AGPL-3.0 and will be published. The obvious route — flip the
existing repository to public — turned out to be a trap.

The history contains things that must never be public: a committed private key
(`docs/dev-license-private.pem`, #116), funding applications, a roadmap with
budget, personal outreach letters, internal host addresses. Removing them from
the *working tree* changes nothing: `git rm` adds a commit, it does not erase.

The remedy would be a history rewrite (`git filter-repo`), a force-push, and
temporarily disabling the branch protection and the mirror. That is a lot of
sharp edges around the one thing you cannot undo — and even then, a Forgejo or
Codeberg instance keeps unreachable objects around for a while, so old commits
stay fetchable by hash until garbage collection runs.

## Decision

**The public repository is a fresh snapshot, created at release, with no prior
history.**

- **Forgejo (private)** stays canonical: full history, issues, PRs, CI. This is
  where the work happens, mistakes included.
- **Codeberg** carries the public snapshot. (Amended 2026-07-17 — this bullet
  read "**Codeberg (private)** stays a push mirror ... a free off-site copy";
  that is not what happened. See the amendment below.)
- **At release**, the sanitized current tree is published to the public
  repository as one commit, AGPL-3.0, no business documents, no keys, no internal
  addresses. (Superseded 2026-07-19: releases *accumulate* — each is one more
  tagged commit on the public history, not a brand-new single-commit repo. See
  the amendment below.)

## Why this is enough

The AGPL requires that users of the service receive the **source code**. It says
nothing about development history. A clean snapshot satisfies the licence in
full.

What we give up is a public commit history. For a solo project that is not a
real loss: there are no outside contributions to look back on, and the `#113`
style references in our commit messages point at a private tracker anyway — in
public they would only confuse.

## What this rules out

Do **not** flip the private repository to public, ever, and do not "just push it
somewhere quickly". The history is not fit for that and never will be. If a
public repository is needed, it is built from a snapshot — see the release
checklist in `docs/business.de.md` (private) and #116.

## Amendment (2026-07-17)

**Codeberg is public, and it is where the snapshot lives.** The Decision above
described Codeberg as a private off-site copy, with the public repository to be
created somewhere unnamed. The decision was carried out; the description was
not kept in step. As of today `codeberg.org/openavisio/openavisio` is public
(`"private": false`), one commit, AGPL-3.0 — `docs/dev-license-private.pem`
returns 404 and no business documents are present. The snapshot is clean and
this ADR's intent holds. Only the label was wrong.

This matters beyond tidiness: the stale line reads as "nothing of ours is
public yet", which is the opposite of the truth, and it invites exactly the
mistake this ADR exists to prevent.

**GitHub joins as a second public mirror**, read-only, for ADR 034 — Proxmox
community-scripts install and update from GitHub Releases, so the snapshot must
be reachable there and tagged.

**The rule is unchanged and now covers two remotes.** Public mirrors are fed
from the snapshot, never from Forgejo. `origin` holds the history that must
never be published, and one `git push github --all` from a working copy of it
would publish the committed private key permanently — the same irreversible
mistake, at a new address. Push from canonical to any public remote stays
disabled; the `codeberg` remote's push URL is already
`DISABLED_use_the_forgejo_mirror`, and the GitHub remote gets the same
treatment.

## Amendment (2026-07-19) — the public history accumulates

The original "fresh snapshot, no history — a new single-commit repo each
release" was wrong about the *shape*, not the intent. A brand-new one-commit
repo every release throws away tags and rewrites `main`, which:

- breaks F-Droid, which pins each build to a persistent commit/tag in the public
  repo and follows tags forward (#60);
- breaks ADR 034's "install/update from GitHub Releases", which needs the
  releases (and their tags) to keep existing;
- and simply wasn't what was wanted — a public project should show its released
  versions over time, not amnesia at every release.

**New shape:** the public repo carries an *accumulating* history — **one
sanitized commit per release, each annotated-tagged `vX.Y.Z`**, committed on top
of the previous release. `main` fast-forwards; it is never force-pushed.

**The security property is unchanged and is still the whole point.** Every public
commit is a freshly sanitized *tree* (`git archive <tag>` → strip internal →
guard), never the private `.git`. The private development history — with the
committed key and business docs — is still never pushed anywhere. What
accumulates publicly is a chain of clean release snapshots, not our real history.

`scripts/make-public-snapshot.sh` implements this: it clones the public repo,
replaces the tree with the new sanitized snapshot of the release tag, commits,
tags, and leaves `main` + the tag ready to push. It aborts if the guard finds
anything internal.
