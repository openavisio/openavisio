# Hosted Deployments pull prebuilt images, they do not build on the box

**Status:** accepted (2026-07-26)

**Depends on:** ADR 024 (one Deployment per customer, isolated in its own LXC)

`deploy/deploy.sh` streams a tag's tree over SSH and runs
`docker compose up -d --build` on the customer box. Its own closing comment says
what this ADR now acts on:

> ponytail: full rebuild + build-on-box every deploy. Fine for a handful of
> LXCs; move to a prebuilt registry image when the build time starts to hurt.

It hurts as soon as Deployments are sold to individuals. ADR 034 sizes an
installation at 6144 MB and states plainly that the RAM is for the `next build`
spike rather than for running the software. Paying for that spike once per
customer per release, on every box, is the whole reason per-customer isolation
looks expensive — and it is an artefact of the deploy method, not of ADR 024.

## The decision

**CI builds `backend`, `aiservice` and `frontend` once per release tag and
pushes them to a registry.** A customer box pulls and starts them. No source
tree is streamed to hosted boxes and no Node toolchain is installed there.

**Provisioning is a clone of a golden LXC template** that already contains Docker
and the current images. Creating a Deployment is then: clone, write `.env`,
`up`, add the proxy host. Seconds, not a build.

**Migrations are unaffected.** The backend image already runs
`alembic upgrade head` before uvicorn, and the health gate in `deploy.sh` stays
as it is.

**Self-hosters are unaffected.** The Compose file keeps building from source, and
the bare-metal path from ADR 034 keeps building in the container. This ADR
changes how *hosted* Deployments are updated, nothing else.

## Consequences

**Good:**
- Per-Deployment RAM drops to what the software actually needs, which is what
  makes one LXC per paying individual affordable
- Every hosted customer runs a bit-identical image, so "which version is this
  Deployment running" has an exact answer, as the DPIA requires
- Rollout time stops scaling with customer count

**Trade-offs:**
- A registry to run, secure and pay for, and a CI job that can now break
  releases for everyone at once rather than one box at a time
- A third thing that can drift from the Compose file, beside the ADR 034
  install script
- Rollback is still "redeploy the previous tag" and is still only safe when the
  migrations were backward-compatible. Prebuilt images make the redeploy faster,
  not the migration reversible.
