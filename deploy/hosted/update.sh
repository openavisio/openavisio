#!/usr/bin/env bash
# Bring hosted Deployments on the box to TAG from hosted.env, one at a time, and stop at the first
# that does not come back. Runs on the operator's machine, from a checkout, like provision.sh.
#
#   deploy/hosted/update.sh             # every running Deployment
#   deploy/hosted/update.sh k7f3x9q2    # only these
#
# A suspended Deployment (site file renamed to .off) is skipped: `up -d` would start it again.
# There is no backup step of its own: it refuses a Deployment whose nightly backup is older than
# 26 h, so run it after the night's backup and the Storage Box snapshot hold the state before.
set -euo pipefail

CONF=${HOSTED_ENV:-$HOME/.config/openavisio/hosted.env}
BOX=$(sed -n 's/^BOX=//p' "$CONF"); TAG=$(sed -n 's/^TAG=//p' "$CONF")
SUFFIX=$(sed -n 's/^DOMAIN_SUFFIX=//p' "$CONF"); SUFFIX=${SUFFIX:-openavisio.app}
: "${BOX:?}" "${TAG:?}"
REF=${REF:-$TAG}
here=$(cd "$(dirname "$0")" && pwd)
F="-f docker-compose.prod.yml -f docker-compose.hosted.yml -f docker-compose.shared-box.yml"

ids=${*:-$(ssh "$BOX" 'for s in /opt/edge/sites/*.caddy; do [ -e "$s" ] && basename "$s" .caddy; done; true')}
[ -n "$ids" ] || { echo "no running Deployment on $BOX"; exit 0; }

for ID in $ids; do
  D=/opt/openavisio-$ID
  echo "==> $ID to $TAG"
  ssh "$BOX" "test -e /opt/edge/sites/$ID.caddy" || { echo "$ID is not routed (suspended?), skipped"; continue; }
  ssh "$BOX" "find /opt/backups/$ID/.last-success -mmin -1560" | grep -q . \
    || { echo "$ID has no backup from the last 26 h, not updating it" >&2; exit 1; }

  (cd "$here/../.." && git archive "$REF" deploy/docker-compose.prod.yml deploy/docker-compose.hosted.yml \
    deploy/docker-compose.shared-box.yml) | ssh "$BOX" "tar -x -C $D --strip-components=1"
  ssh "$BOX" "cd $D && sed -i 's/^TAG=.*/TAG=$TAG/' .env && docker compose $F pull -q \
    && docker compose $F up -d --no-build 2>&1 | tail -1 \
    && for i in \$(seq 1 60); do \
         [ \"\$(docker inspect -f '{{.State.Health.Status}}' oa-$ID-backend-1)\" = healthy ] && exit 0; sleep 5; done; \
       echo 'backend never became healthy' >&2; exit 1"

  # up -d may recreate the network, and Caddy loses its attachment; the check proves it is back
  ssh "$BOX" "docker network connect oa-${ID}_default edge-caddy-1" 2>/dev/null || true
  ssh "$BOX" "docker network connect oa-${ID}_default edge-llm-proxy-1" 2>/dev/null || true
  ssh "$BOX" "sh -s -- $ID" < "$here/isolation-check.sh"
  code=$(curl -s -o /dev/null -w '%{http_code}' "https://$ID.$SUFFIX/" || true)
  [ "$code" = 307 ] || { echo "https://$ID.$SUFFIX answers $code" >&2; exit 1; }
  echo "    $ID is on $TAG"
done
