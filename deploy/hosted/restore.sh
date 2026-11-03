#!/usr/bin/env bash
# Restore one hosted Deployment from the Storage Box into a NEW Deployment on a box with the shared
# Caddy: the drill, and the real thing after a lost box or a broken instance (docs/backup-restore.md).
#
#   AGE_KEY=~/.config/openavisio/age-restore.key deploy/hosted/restore.sh <old-id> [YYYY-MM-DD]
#
# Runs on the operator's machine. The age private key never leaves it: every stream is decrypted
# here and piped over ssh. The new Deployment gets a fresh id and the old one's master KEK from the
# escrow, so its documents open. Needs hosted.env (BOX, ESCROW_DEST) like provision.sh.
set -euo pipefail
OLD=${1:?old deployment id}
DAY=${2:-$(date +%F)}
: "${AGE_KEY:?path to the age private key}"
CONF=${HOSTED_ENV:-$HOME/.config/openavisio/hosted.env}
BOX=$(sed -n 's/^BOX=//p' "$CONF"); SB=$(sed -n 's/^ESCROW_DEST=//p' "$CONF")
REGISTRY=$(sed -n 's/^REGISTRY=//p' "$CONF"); TAG=$(sed -n 's/^TAG=//p' "$CONF")
here=$(cd "$(dirname "$0")" && pwd)

W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
rsync -rt -e "ssh -p23" "$SB:backups/$OLD/clinical-$DAY.sql.age" "$SB:backups/$OLD/keystore-$DAY.sql.age" \
  "$SB:escrow/$OLD.kek.age" "$W/"
# documents: the restic repository since #341, a nightly tarball before it; the day of the switch has both
rsync -rt -e "ssh -p23" "$SB:backups/$OLD/documents" "$SB:backups/$OLD/restic-password.age" "$W/" 2>/dev/null || true
rsync -rt -e "ssh -p23" "$SB:backups/$OLD/documents-$DAY.tar.gz.age" "$W/" 2>/dev/null || true
[ -d "$W/documents" ] || [ -f "$W/documents-$DAY.tar.gz.age" ] || { echo "no document backup of $OLD for $DAY" >&2; exit 1; }
KEK=$(age -d -i "$AGE_KEY" "$W/$OLD.kek.age")

# 1. A new Deployment with the old KEK: stack up, isolation checked, certificate in place.
ID=${ID:-$(tr -dc a-z0-9 </dev/urandom | head -c 8 || true)}
(cd "$here/../.." && ID=$ID KEK=$KEK "$here/provision.sh") | grep -v '#token=' || true
unset KEK
D=/opt/openavisio-$ID
F="-f docker-compose.prod.yml -f docker-compose.hosted.yml -f docker-compose.shared-box.yml"
on_box() { ssh "$BOX" "cd $D && $*"; }

# 2. Everything but Postgres down, the fresh database replaced by the backup's.
on_box "docker compose $F stop backend celery-worker celery-worker-gpu celery-beat frontend backup aiservice >/dev/null 2>&1"
on_box "docker compose $F exec -T postgres sh -c 'psql -q -U \$POSTGRES_USER -d postgres -c \"DROP DATABASE vaultdb\" -c \"CREATE DATABASE vaultdb\"'"
for s in clinical keystore; do
  age -d -i "$AGE_KEY" "$W/$s-$DAY.sql.age" \
    | on_box "docker compose $F exec -T postgres sh -c 'psql -q -v ON_ERROR_STOP=1 -U \$POSTGRES_USER -d vaultdb' >/dev/null"
done
restored=
if [ -d "$W/documents" ]; then
  R=/tmp/oa-restore-$ID
  tar -C "$W" -c documents | ssh "$BOX" "rm -rf $R && mkdir -p $R && tar -x -C $R"
  # the password goes on stdin, never on a command line; --no-lock because the copy is read-only
  { age -d -i "$AGE_KEY" "$W/restic-password.age"; echo; } | ssh "$BOX" "docker run --rm -i --entrypoint sh \
    -v $R/documents:/repo:ro -v oa-${ID}_document-data:/data/documents $REGISTRY/openavisio/backup:$TAG \
    -c 'read -r RESTIC_PASSWORD; export RESTIC_PASSWORD; restic -r /repo --no-cache --no-lock restore latest --host openavisio --tag $DAY --target /'; rc=\$?; rm -rf $R; exit \$rc" \
    && restored=restic
fi
if [ -z "$restored" ] && [ -f "$W/documents-$DAY.tar.gz.age" ]; then
  [ -d "$W/documents" ] && echo "no restic snapshot for $DAY, using the tarball" >&2
  age -d -i "$AGE_KEY" "$W/documents-$DAY.tar.gz.age" \
    | ssh "$BOX" "docker run --rm -i -v oa-${ID}_document-data:/data/documents -w /data/documents alpine:3.21 tar -xz" \
    && restored=tarball
fi
[ -n "$restored" ] || { echo "documents of $OLD ($DAY) could not be restored; $ID is left as it is" >&2; exit 1; }
echo "documents restored from the $restored backup"

# 3. Up again, and a document must decrypt end to end, not merely exist as a row.
on_box "docker compose $F up -d --no-build >/dev/null 2>&1"
for _ in $(seq 1 60); do
  [ "$(ssh "$BOX" docker inspect -f '{{.State.Health.Status}}' oa-$ID-backend-1)" = healthy ] && break; sleep 5
done
on_box "docker compose $F exec -T backend uv run python -" <<'PY'
import asyncio
from sqlalchemy import func, select
from app.core.database import AsyncSessionLocal
from app.models.document import DocumentReference
from app.core.patient_keys import get_patient_kek
from app.core.encryption import decrypt_document
from app.core.storage import get_storage

async def main():
    async with AsyncSessionLocal() as db:
        n = await db.scalar(select(func.count()).select_from(DocumentReference))
        doc = (await db.execute(select(DocumentReference).limit(1))).scalars().first()
        if not doc:
            raise SystemExit("restored, but there is no document to prove the keys with")
        kek = await get_patient_kek(db, doc.patient_id)
        data = decrypt_document(get_storage().read(doc.storage_path), doc.encrypted_dek, kek)
        print(f"OK: {n} documents, one decrypted end to end: {len(data)} bytes, starts {data[:5]!r}")
asyncio.run(main())
PY
echo "Restored $OLD ($DAY) as https://$ID.openavisio.app; sign in with the old accounts."
