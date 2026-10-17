#!/bin/sh
# Run on a hosted box (provision.sh does it after every new Deployment):
#   ssh root@<box> 'sh -s' < deploy/hosted/isolation-check.sh        # all Deployments
#   ssh root@<box> 'sh -s -- <id>' < deploy/hosted/isolation-check.sh  # only pairs that involve <id>
# Exit 1 and a FAIL line for each way one Deployment could reach another, or Caddy could not
# reach one. Deployments are Compose projects named oa-<id>, each with its own default network.
set -u
CADDY=${CADDY:-edge-caddy-1}
ONLY=${1:-}
bad=0
fail() { echo "FAIL: $*"; bad=1; }
ids=$(docker network ls --format '{{.Name}}' | sed -n 's/^oa-\([a-z0-9]*\)_default$/\1/p')

for id in $ids; do
  members=$(docker network inspect -f '{{range .Containers}}{{.Name}} {{end}}' "oa-${id}_default")
  for c in $members; do
    case "$c" in "oa-$id-"*|"$CADDY") ;; *) fail "$c is on the network of $id" ;; esac
  done
  echo " $members" | grep -q " $CADDY " || fail "$CADDY is not on the network of $id, so $id is unreachable"
done

# a Deployment's containers sit on its own network and nowhere else
for c in $(docker ps --format '{{.Names}}' | grep '^oa-'); do
  id=$(echo "$c" | cut -d- -f2)
  [ -n "$ONLY" ] && [ "$ONLY" != "$id" ] && continue
  for n in $(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$c"); do
    [ "$n" = "oa-${id}_default" ] || fail "$c is also on the network $n"
  done
done

# and the wire agrees: no frontend can open another Deployment's backend
for a in $ids; do
  [ -n "$ONLY" ] && [ "$ONLY" != "$a" ] && continue
  for b in $ids; do
    [ "$a" = "$b" ] && continue
    ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "oa-$b-backend-1" 2>/dev/null | cut -d' ' -f1)
    [ -n "$ip" ] || continue
    if docker exec "oa-$a-frontend-1" wget -qO- -T 2 "http://$ip:8000/health" >/dev/null 2>&1; then
      fail "the frontend of $a reaches the backend of $b"
    fi
  done
done

[ "$bad" = 0 ] && echo "isolation ok ($(echo $ids | wc -w) Deployments)"
exit $bad
