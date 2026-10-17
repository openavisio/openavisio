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
here=$(cd "$(dirname "$0")" && pwd)

W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
rsync -rt -e "ssh -p23" "$SB:backups/$OLD/clinical-$DAY.sql.age" "$SB:backups/$OLD/keystore-$DAY.sql.age" \
  "$SB:backups/$OLD/documents-$DAY.tar.gz.age" "$SB:escrow/$OLD.kek.age" "$W/"
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
age -d -i "$AGE_KEY" "$W/documents-$DAY.tar.gz.age" \
  | ssh "$BOX" "docker run --rm -i -v oa-${ID}_document-data:/data/documents -w /data/documents alpine:3.21 tar -xz"

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
