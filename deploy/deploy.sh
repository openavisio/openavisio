#!/bin/sh
# Deploy a tagged release to a customer LXC (ADR 024). Push model: stream the
# tag's tree over SSH, rebuild, wait for health. See docs/deployment.md.
#
#   ./deploy/deploy.sh <ssh-target> <tag> [remote-dir]
#   ./deploy/deploy.sh root@dup15q-box v0.1.0
#
# Safe by construction: `git archive` contains only TRACKED files, so the box's
# untracked .env, data/, and backups/ are never in the stream and cannot be
# overwritten. No --delete anywhere, so no data dir can be pruned.
set -eu

usage() { echo "usage: $0 <ssh-target> <tag> [remote-dir]" >&2; exit 2; }
[ $# -ge 2 ] || usage
TARGET=$1
TAG=$2
DIR=${3:-/opt/openavisio}

# Deploy only a real, pushed, annotated tag — never a branch or a local-only
# tag. git archive reads the tag's tree from the object store, so a dirty
# working tree is irrelevant: the deployed state is exactly the tag.
git rev-parse -q --verify "refs/tags/$TAG^{tag}" >/dev/null 2>&1 \
  || { echo "not an annotated tag: $TAG (see docs/releasing.md)" >&2; exit 1; }
git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1 \
  || { echo "tag $TAG is not on origin — push it first" >&2; exit 1; }

echo "==> deploying $TAG to $TARGET:$DIR"
git archive --format=tar "$TAG" | ssh "$TARGET" "tar -x --no-same-owner -C '$DIR'"

# Rebuild + recreate, then wait for the backend to report healthy. The backend
# container's CMD runs 'alembic upgrade head' before uvicorn, so migrations run
# here automatically; its healthcheck already probes DB + Redis (#115). Passing
# DIR as $1 keeps the remote script single-quoted (no local/remote expansion mix).
ssh "$TARGET" "sh -s -- '$DIR'" <<'REMOTE'
set -eu
cd "$1"
docker compose up -d --build
cid=$(docker compose ps -q backend)
echo "==> waiting for backend health"
i=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null)" = healthy ]; do
  i=$((i + 1))
  if [ "$i" -ge 40 ]; then
    echo "FAIL: backend not healthy after ~200s — rolling nothing back, box left as-is" >&2
    docker compose logs --tail=40 backend >&2
    exit 1
  fi
  sleep 5
done
docker compose ps
REMOTE

echo "==> OK — $TAG live on $TARGET"
# ponytail: full rebuild + build-on-box every deploy. Fine for a handful of
# LXCs; move to a prebuilt registry image when the build time starts to hurt.
# Rollback = redeploy the previous tag, which is only safe if migrations are
# backward-compatible — the script can't enforce that, the health gate only
# makes a broken deploy visible immediately.
