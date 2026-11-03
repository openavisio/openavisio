# Document backups are a restic repository

The nightly backup wrote every document blob into one age-encrypted tarball and kept 90 of them. The blobs are ciphertext and never change once written, so nothing compressed and nothing was shared between nights: backup space grew with 90 times the live volume. On the hosted box, 30 MB of documents had become 918 MB of backups after 16 days. A household scanning its paper would fill its share of the box in the first year, and a care home would fit nowhere (#341).

## The decision

**The documents go into a restic repository in the backup directory, one snapshot per night.** restic stores each blob once, however many snapshots hold it, so 90 days of history cost about the live volume plus what was added. Each snapshot is tagged with its date and a fixed host name, so a restore picks the snapshot of the same day as its clinical and keystore dumps, and `restic forget --keep-within 90d --prune` keeps exactly the old retention. After every backup `restic check` runs, and the snapshot must hold as many entries as the volume; otherwise the run fails and the healthcheck turns unhealthy.

**The repository has its own password, kept in two places.** `RESTIC_PASSWORD` is in the Deployment's `.env`, because the backup must write unattended. The backup also writes `restic-password.age` beside the repository, encrypted to the age key, so a restore after a lost box needs nothing beyond what it needed before: the age key and the master KEK.

**The clinical and keystore dumps stay as they are.** They are small, and the keystore's short retention is what lets crypto-shredding reach backups (ADR 031). The keystore never goes into the repository.

## Alternatives, and why not

- **Git.** Made for text that changes. On ciphertext that never changes it saves nothing, and an old state can only go by rewriting history, so neither the 90-day retention nor the erasure guarantee would hold.
- **rsync into one directory, history from the Storage Box snapshots.** A BX11 keeps 10 snapshots, so a deleted document would be gone after 10 days instead of 90.
- **borg.** Equally proven, but its remote mode needs borg on the other side. restic writes into a plain directory that the existing push mirrors.

## Consequences

- Installs from before this change need `RESTIC_PASSWORD` in `.env`: `setup.sh` adds a missing one on its next run, `provision.sh` sets it for new hosted Deployments, and `update.sh` adds it to existing ones, generated on the box. Without it the backup refuses to run and says why.
- The old `documents-*.tar.gz.age` files age out after 90 days. `deploy/hosted/restore.sh` restores either kind and takes the restic snapshot when a day has both.
- A pull target (variant A in `docs/backup-restore.md`) mirrors the repository with `--delete`, because restic prunes inside it; filesystem snapshots on the target protect it instead.
