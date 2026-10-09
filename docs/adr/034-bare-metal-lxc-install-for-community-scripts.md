# ADR 034: A second, bare-metal install path for Proxmox community-scripts

**Status:** accepted (2026-07-17)

**In tension with:** ADR 024 (one Deployment per customer, isolated in its own LXC) —
which promises the software stays identical for hosted customers and self-hosters.
This ADR knowingly breaks that promise for one distribution channel. Read the
Trade-offs before extending it.

**Depends on:** ADR 032 amendment (GitHub mirror, tagged releases)

## Context

[Proxmox VE Helper-Scripts](https://community-scripts.org/) is where a large part
of the homelab audience finds self-hostable software. An entry there is a
distribution channel we cannot buy and cannot replicate.

Their rule is not negotiable, and it is stated flatly in their contribution
guidelines for AI assistants:

> **Bare-Metal Installation.** We do **NOT** use Docker for our installation
> scripts. All applications are installed directly on the system.

This is not a preference they bend for awkward stacks. Immich upstream ships
only a Compose file; community-scripts answered with a 572-line native installer
that reimplements the stack service by service, down to scraping upstream's
Dockerfile for pinned GPU driver versions. That is the price of the shelf space.

OpenAvisio ships as nine Compose services built from source. So the choice was:
stay off the shelf, or own a second install path that we do not run ourselves.
We are taking the shelf.

Two facts made the cost tolerable, both established by reading the code rather
than assuming:

- **Nothing needs a GPU.** `celery-worker-gpu` has no device mapping, no
  `runtime: nvidia`, no reservations. It is an ordinary worker on a queue
  *named* `gpu` at `--concurrency=1`, carrying `ocr_stage`, `extraction_stage`
  and `embedding_stage` — all of which call out to `aiservice`, which ships only
  the `ollama` and `openai` **clients**. No torch, no transformers, no weights.
  The name is a lie the LXC would otherwise inherit; it cost a reviewer three
  wrong turns already. No passthrough, no `setup_hwaccel`.
- **pgvector is one line** there: `PG_VERSION="17" PG_MODULES="pgvector"`.

## Decision

**Ship a native LXC install script to ProxmoxVED**, alongside — never replacing —
the Compose stack. New scripts go to ProxmoxVED first; PRs against ProxmoxVE are
closed unreviewed.

One unprivileged Debian 13 container, 4 CPU / 6144 MB / 20 GB (Immich's defaults;
the RAM is for the `next build` spike, not for runtime).

### What runs

Postgres 17 + pgvector, Redis, Caddy, and six OpenAvisio systemd units:
`backend`, `celery-worker`, `celery-worker-gpu`, `celery-beat`, `aiservice`
(with tesseract/ocrmypdf from apt), `frontend` (`next start` — Next.js SSR, not
static files).

- **Caddy is not optional and is not about TLS.** The `Caddyfile` is the path
  router: `/api/auth/*`, `/api/upload/*`, `/api/documents/*/file` and friends to
  the frontend, `/api/backend/*` rewritten to the backend with
  `flush_interval -1` for chat streaming. Without it the app does not route. It
  binds `:80`; the operator brings their own TLS proxy.
- **Migrations come free.** The backend Dockerfile already runs
  `alembic upgrade head && uvicorn`; the unit does the same via `ExecStartPre`,
  workers order `After=` it. No update-time migration logic to invent.
- **Built from source in the container.** No prebuilt artifacts, so the release
  process stays "tag and snapshot" and CI gains nothing to maintain. Costs
  install time and leaves the Node toolchain on the box.

### State lives outside `/opt`

`/etc/openavisio/openavisio.env` (0600 root) and `/var/lib/openavisio/documents`.
`/opt/openavisio` holds code only.

This is the one decision here that is not a preference. `DOCUMENT_ENCRYPTION_KEY`
is the KEK; under ADR 022 losing it makes every document permanently
unrecoverable. The community-scripts update idiom is
`CLEAN_INSTALL=1 fetch_and_deploy_gh_release`, which wipes the app directory —
their own template works around it by copying state out and back, which is a
crash window over the one thing that cannot be restored. Keeping state outside
`/opt` means the update *cannot* reach the key, rather than being careful not to.

### First run

Three prompts, all skippable, none blocking the install:

- **Public URL** (default `http://<LXC-IP>`) — drives passkey origin, share links
  (ADR 021) and invitation mail. Passkeys need a real HTTPS origin to work at
  all, but nobody is locked out without one: ADR 014 guarantees every User keeps
  a password.
- **AI backend URL**, blank allowed — the app installs and runs; the assistant
  stays dark until configured. Weights are never bundled. Consistent with
  ADR 005 (the backend URL is install-time config, model choice is admin UI).
- **AGE_PUBKEY**, blank allowed — see Backups.

The script **must print `BOOTSTRAP_TOKEN`**. Production first-run setup verifies
`X-Bootstrap-Token` with `secrets.compare_digest`; without the token on screen
the operator can never create their Organization, and the install is a brick.

### Backups ship, as a systemd timer

`backup.sh` becomes a `.timer` (needs `age`, `postgresql-client-17`, `tar`,
`gzip`). Prompt for an age public key; blank installs the timer **disabled**,
never a generated key. The private key stays off the box or the encryption
protects nothing from whoever owns the box.

**`vzdump` is not a substitute.** The three-stream design — clinical, keystore at
*short* retention, documents — is what makes ADR 031 crypto-shredding reach
backups. A Proxmox snapshot copies `patient_keys` at full retention, so an
erased Patient (ADR 017) stays decryptable in every backup. Dropping the timer
would not be an ops shortcut, it would silently void a compliance property we
claim in writing.

### Releases

Semver tag plus a GitHub Release per public snapshot, so
`fetch_and_deploy_gh_release` and `check_for_gh_release` work unmodified. Today
there are no tags anywhere and all three components read `version = "0.1.0"`;
that has to change regardless — a medical product with a DPIA cannot answer
"what version is this Deployment running?" with a shrug.

## Rejected

- **Docker-in-LXC.** Their rule, not ours. The alternative to obeying it is not
  being listed.
- **Our own installer, in our own repo.** No rules to obey and no bare-metal
  rewrite — but also none of the reach, which was the entire point.
- **Bundling Ollama.** Gigabytes of weights and CPU-only inference, to avoid one
  optional prompt.
- **Prebuilt artifacts on the Release.** Faster, smaller box; costs CI that
  builds and pushes to a mirror on every release. Revisit only if install time
  or OOM becomes a real complaint.
- **`vzdump` instead of `backup.sh`.** See above — this one is not a trade-off,
  it is a regression.

## Consequences

**Good:**
- A distribution channel that reaches the homelab audience directly, at the cost
  of a script rather than a marketing budget
- Forces a release/versioning practice we needed anyway
- Far cheaper than the Immich precedent: no GPU, no passthrough, no local models

**Trade-offs:**
- **A second install path we do not run.** Add a service or an env var to Compose
  and the script does not know. It breaks for strangers, silently, and we hear
  about it weeks later as a bug report. Nothing in CI covers it. This is the
  ADR 024 tension made concrete, and it is the reason to keep this path as thin
  as possible.
- **The verdict comes after the work.** OpenAvisio is unreleased, zero stars and
  self-submitted. Their guide sets no popularity bar, but the bare-metal work
  lands before anyone reviews it.
- **A third remote to keep honest.** See the ADR 032 amendment: public mirrors
  are fed from the snapshot, never from Forgejo.
- The `gpu` queue name will mislead every reader of this script until it is
  renamed. Worth doing; deliberately not bundled into this change.
