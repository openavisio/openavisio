#!/bin/sh
# Nightly backup — three streams, age-encrypted, per ADR-022 and ADR-031.
#
#   clinical   everything EXCEPT patient_keys       long retention
#   keystore   ONLY patient_keys                    SHORT retention  <- this is
#              what makes crypto-shredding reach backups: once a patient's KEK
#              has aged out of every keystore backup, the clinical backups still
#              holding their ciphertext are permanently undecryptable.
#   documents  the encrypted blobs on disk          long retention
#
# A restore needs the clinical AND keystore stream OF THE SAME DATE, plus the
# documents tarball, plus the out-of-band DOCUMENT_ENCRYPTION_KEY and age key.
# See docs/backup-restore.md.
set -eu
# pipefail is the whole ballgame here. Without it, `pg_dump | age > file` reports
# success when pg_dump DIES — age happily encrypts the empty stream and exits 0.
# That is exactly what happened on 2026-07-13: Postgres was briefly down, pg_dump
# failed with "connection refused", and the script overwrote a good 25 MB backup
# with a 200-byte encrypted nothing, then logged "ok". A backup system that
# destroys a good backup and reports success is worse than none at all.
set -o pipefail

: "${POSTGRES_USER:?}"
: "${POSTGRES_PASSWORD:?}"
: "${AGE_PUBKEY:?set AGE_PUBKEY (age1...) in deploy/.env}"
PGHOST="${PGHOST:-postgres}"
DB="${POSTGRES_DB:-vaultdb}"
OUT="${BACKUP_DIR:-/backups}"
KEEP_CLINICAL="${RETENTION_CLINICAL_DAYS:-90}"
KEEP_KEYSTORE="${RETENTION_KEYSTORE_DAYS:-7}"
HOUR="${BACKUP_HOUR:-3}"
DOCS="${DOCUMENT_STORAGE_PATH:-/data/documents}"

export PGPASSWORD="$POSTGRES_PASSWORD"

log() { echo "[backup] $(date -Iseconds) $*"; }

run_backup() {
  day=$(date +%F)
  tmp="$OUT/.tmp.$$"
  mkdir -p "$OUT" "$tmp"
  # a half-written backup must never look like a good one: build in a temp dir,
  # move into place only once every stream succeeded
  trap 'rm -rf "$tmp"' EXIT

  # Wait for Postgres instead of dumping nothing. The container restarts with the
  # stack; on 2026-07-13 it ran while Postgres was still coming up.
  i=0
  until pg_isready -h "$PGHOST" -U "$POSTGRES_USER" -q; do
    i=$((i + 1))
    [ "$i" -ge 30 ] && { log "FEHLER: Postgres nach 60s nicht erreichbar — kein Backup"; return 1; }
    sleep 2
  done

  log "clinical dump (excluding patient_keys)"
  pg_dump -h "$PGHOST" -U "$POSTGRES_USER" --exclude-table=patient_keys "$DB" \
    | age -r "$AGE_PUBKEY" > "$tmp/clinical-$day.sql.age"

  log "keystore dump (patient_keys only)"
  pg_dump -h "$PGHOST" -U "$POSTGRES_USER" --table=patient_keys "$DB" \
    | age -r "$AGE_PUBKEY" > "$tmp/keystore-$day.sql.age"

  log "document blobs"
  tar -cz -C "$DOCS" . | age -r "$AGE_PUBKEY" > "$tmp/documents-$day.tar.gz.age"

  # "not empty" is not a check: age of an EMPTY stream is ~200 bytes and sails
  # through `-s`. Demand a plausible size per stream — a real clinical dump of
  # this schema is megabytes, a keystore is at least a kilobyte.
  #
  # documents is the exception: a fresh instance has zero blobs, so its tarball
  # is legitimately ~300 bytes. The floor guards against a TRUNCATED archive of a
  # FULL volume, so only apply it when the volume actually holds files.
  docs_floor=1024
  [ "$(find "$DOCS" -type f 2>/dev/null | head -1 | wc -l)" -eq 0 ] && docs_floor=1
  min_size() {
    case "$1" in
      clinical-*)  echo 65536 ;;   # 64 KB — an empty schema dump is already bigger
      keystore-*)  echo 1024  ;;   # 1 KB
      documents-*) echo "$docs_floor" ;;
      *)           echo 1     ;;
    esac
  }

  for f in "$tmp"/*; do
    name=$(basename "$f")
    size=$(wc -c < "$f")
    min=$(min_size "$name")
    if [ "$size" -lt "$min" ]; then
      log "FEHLER: $name ist nur ${size} Bytes (erwartet >= ${min}) — Abbruch, NICHTS wird veröffentlicht"
      log "        die bestehende Sicherung dieses Tages bleibt unangetastet."
      return 1
    fi
  done

  # only now, with every stream proven plausible, replace the day's files
  for f in "$tmp"/*; do
    mv "$f" "$OUT/"
  done
  rm -rf "$tmp"; trap - EXIT

  log "prune: clinical/documents > ${KEEP_CLINICAL}d, keystore > ${KEEP_KEYSTORE}d"
  find "$OUT" -maxdepth 1 -name 'clinical-*.sql.age'      -mtime "+$KEEP_CLINICAL" -delete
  find "$OUT" -maxdepth 1 -name 'documents-*.tar.gz.age'  -mtime "+$KEEP_CLINICAL" -delete
  find "$OUT" -maxdepth 1 -name 'keystore-*.sql.age'      -mtime "+$KEEP_KEYSTORE" -delete

  touch "$OUT/.last-success"
  log "ok — $(du -sh "$OUT" | cut -f1) belegt, $(ls -1 "$OUT"/clinical-* 2>/dev/null | wc -l) klinische Stände"
}

# one immediate run on start, so a fresh deployment is covered tonight-minus-one
# and a broken config is discovered now rather than at 03:00
if ! run_backup; then
  log "FEHLER beim ersten Lauf"
fi

while true; do
  # busybox date has no `-d "today 3:00"` — it silently fell back to "in 24h",
  # so the job drifted to whenever the container happened to start. Compute the
  # delay from the local wall clock instead.
  # Strip the leading zero: ash reads `08`/`09` as octal and dies with an
  # arithmetic error (crashloop every day between 08:00 and 09:59).
  now_h=$(date +%H); now_m=$(date +%M); now_s=$(date +%S)
  secs_now=$(( ${now_h#0} * 3600 + ${now_m#0} * 60 + ${now_s#0} ))
  delay=$(( HOUR * 3600 - secs_now ))
  [ "$delay" -le 0 ] && delay=$(( delay + 86400 ))
  log "nächster Lauf um ${HOUR}:00 (in $(( delay / 60 )) min)"
  sleep "$delay"
  run_backup || log "FEHLER — Lauf fehlgeschlagen, .last-success bleibt alt (Healthcheck schlägt an)"
done
