#!/usr/bin/env bash
# One line per hosted Deployment on every box: which version it runs, whether it is routed, healthy
# and backed up, and whether update.sh still has to bring it to TAG from hosted.env.
#
#   deploy/hosted/status.sh
#
# The boxes are BOXES in hosted.env (space-separated ssh targets), or the one BOX.
set -euo pipefail

CONF=${HOSTED_ENV:-$HOME/.config/openavisio/hosted.env}
TAG=$(sed -n 's/^TAG=//p' "$CONF")
BOXES=$(sed -n 's/^BOXES=//p' "$CONF"); BOXES=${BOXES:-$(sed -n 's/^BOX=//p' "$CONF")}
: "${BOXES:?}"

printf '%-22s %-10s %-8s %-9s %-9s %-11s %s\n' BOX ID VERSION ROUTED HEALTH BACKUP "TO $TAG"
for BOX in $BOXES; do
  ssh -o ConnectTimeout=10 "$BOX" 'for e in /opt/openavisio-*/.env; do
      [ -e "$e" ] || continue
      d=$(dirname "$e"); id=${d#/opt/openavisio-}
      tag=$(sed -n "s/^TAG=//p" "$e")
      if [ -e /opt/edge/sites/$id.caddy ]; then r=yes; else r=suspended; fi
      h=$(docker inspect -f "{{.State.Health.Status}}" oa-$id-backend-1 2>/dev/null || echo down)
      b=/opt/backups/$id/.last-success
      if [ -e "$b" ]; then a="$(( ($(date +%s) - $(stat -c %Y "$b")) / 3600 )) h ago"; else a=never; fi
      echo "$id $tag $r $h $a"
    done' | while read -r id tag r h a1 a2 a3; do
    due=$([ "$tag" = "$TAG" ] && echo - || echo due)
    printf '%-22s %-10s %-8s %-9s %-9s %-11s %s\n' "$BOX" "$id" "$tag" "$r" "$h" "$a1 ${a2:-} ${a3:-}" "$due"
  done
done
