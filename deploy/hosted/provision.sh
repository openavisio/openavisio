#!/usr/bin/env bash
# Provision one hosted Deployment on a box that already has Docker, the registry login and the
# shared Caddy (deploy/hosted/docker-compose.edge.yml). Runs on the operator's machine, from a
# checkout, and talks to the box over SSH. ADR 0007 (avisiohub), amended.
#
#   deploy/hosted/provision.sh              # a fresh random id
#   ID=k7f3x9q2 deploy/hosted/provision.sh  # a given id (tests, re-runs after a delete)
#
# Needs ~/.config/openavisio/hosted.env (mode 600, never in git) with:
#   BOX=root@203.0.113.10     BOX_IP=203.0.113.10     REGISTRY=registry.example.org
#   TAG=v0.1.0-beta10         DOMAIN_SUFFIX=openavisio.app
#   AGE_PUBKEY=age1...        the same mail values for every Deployment:
#   SMTP_USER=...  SMTP_PASSWORD=...  SMTP_FROM=...  OPS_ALERT_EMAIL=...
# The IONOS token is not here: it lives in the box's LLM proxy (/opt/edge/.env), and each
# Deployment gets its own proxy key from proxy-key.sh (#375).
#   optional: ESCROW_DEST=u123456@u123456.your-storagebox.de   (escrow copy off this machine)
#
# After the stack is up it attaches the shared Caddy to the Deployment's own network and refuses to
# route it if isolation-check.sh finds a way between Deployments.
#
# What it does not do yet: the Storage Box sub-account and the backup push, the Uptime Kuma
# monitor, and the A record at INWX. The A record is the one thing that waits for a person.
set -euo pipefail

CONF=${HOSTED_ENV:-$HOME/.config/openavisio/hosted.env}
[ -r "$CONF" ] || { echo "missing $CONF" >&2; exit 1; }
# KEY=VALUE as plain text, never sourced: a value may hold spaces, parentheses or a "$".
while IFS='=' read -r k v; do
  case "$k" in ''|\#*) continue ;; esac
  export "$k=$v"
done < "$CONF"
: "${BOX:?}" "${BOX_IP:?}" "${REGISTRY:?}" "${TAG:?}" "${AGE_PUBKEY:?}" \
  "${SMTP_USER:?}" "${SMTP_PASSWORD:?}" "${SMTP_FROM:?}" "${OPS_ALERT_EMAIL:?}"
SUFFIX=${DOMAIN_SUFFIX:-openavisio.app}
REF=${REF:-$TAG}   # the git ref the compose files come from

ID=${ID:-$(tr -dc a-z0-9 </dev/urandom | head -c 8 || true)}   # SIGPIPE from head is not an error
HOST=$ID.$SUFFIX
DIR=/opt/openavisio-$ID
ESCROW_DIR=${ESCROW_DIR:-$HOME/.local/share/openavisio/escrow}

# 1. The A record. Caddy asks for the certificate when the site file loads, and a request for a
#    name that does not resolve burns Let's Encrypt rate limit, so wait here.
if [ "$(dig +short "$HOST" A @ns.inwx.de)" != "$BOX_IP" ]; then
  echo "Set this A record at INWX, then wait:   $ID   A   $BOX_IP"
  for _ in $(seq 1 90); do
    [ "$(dig +short "$HOST" A @ns.inwx.de)" = "$BOX_IP" ] && break
    sleep 10
  done
  [ "$(dig +short "$HOST" A @ns.inwx.de)" = "$BOX_IP" ] || { echo "no A record for $HOST" >&2; exit 1; }
fi

# 2. Secrets. The master KEK is the only one that must survive the box: it goes to an
#    age-encrypted file that only the operator's private key opens, before anything is started.
rnd() { openssl rand -hex "$1"; }
KEK=${KEK:-$(openssl rand -base64 32)}   # restore.sh passes the escrowed one
mkdir -p "$ESCROW_DIR"; chmod 700 "$ESCROW_DIR"
printf '%s' "$KEK" | age -r "$AGE_PUBKEY" -o "$ESCROW_DIR/$ID.kek.age"
if [ -n "${ESCROW_DEST:-}" ]; then
  ssh -p23 "$ESCROW_DEST" mkdir -p escrow 2>/dev/null || true
  rsync -a -e "ssh -p23" "$ESCROW_DIR/$ID.kek.age" "$ESCROW_DEST:escrow/"
else
  echo "WARNING: the key escrow for $ID exists only on this machine ($ESCROW_DIR)." >&2
fi
BOOTSTRAP=$(rnd 24)

# 3. The files, from the release, no source tree. The .env travels on stdin, not on a command line.
git archive "$REF" deploy/docker-compose.prod.yml deploy/docker-compose.hosted.yml \
  deploy/docker-compose.shared-box.yml | ssh "$BOX" "mkdir -p $DIR && tar -x -C $DIR --strip-components=1"
ssh "$BOX" "umask 077; mkdir -p /opt/backups/$ID; cat > $DIR/.env" <<EOF
COMPOSE_PROJECT_NAME=oa-$ID
INSTANCE_ID=$ID
HOSTED_SETUP=true
REGISTRY=$REGISTRY
TAG=$TAG
DOMAIN=$HOST
BACKUP_DIR=/opt/backups/$ID
POSTGRES_USER=openavisio
POSTGRES_PASSWORD=$(rnd 24)
APP_SECRET=$(rnd 32)
AISERVICE_TOKEN=$(rnd 24)
BOOTSTRAP_TOKEN=$BOOTSTRAP
DOCUMENT_ENCRYPTION_KEY=$KEK
AGE_PUBKEY=$AGE_PUBKEY
AI_BACKEND=vllm
VLLM_URL=http://edge-llm-proxy-1:8080/v1
VLLM_EMBED_URL=http://edge-llm-proxy-1:8080/v1
VLLM_API_KEY=
VLLM_MODEL=Qwen/Qwen3.8-27B
VLLM_VISION_MODEL=lightonai/LightOnOCR-2-1B
VLLM_EMBED_MODEL=Qwen/Qwen3-VL-Embedding-8B
SMTP_HOST=smtp.mailbox.org
SMTP_PORT=587
SMTP_USER=$SMTP_USER
SMTP_PASSWORD=$SMTP_PASSWORD
SMTP_FROM=$SMTP_FROM
OPS_ALERT_EMAIL=$OPS_ALERT_EMAIL
EOF

# 4. Start, and wait for the backend to say it is healthy.
ssh "$BOX" "cd $DIR && F='-f docker-compose.prod.yml -f docker-compose.hosted.yml -f docker-compose.shared-box.yml' \
  && docker compose \$F pull -q && docker compose \$F up -d --no-build 2>&1 | tail -1 \
  && for i in \$(seq 1 60); do \
       [ \"\$(docker inspect -f '{{.State.Health.Status}}' oa-$ID-backend-1)\" = healthy ] && exit 0; sleep 5; done; \
     echo 'backend never became healthy' >&2; exit 1"

# 4b. Caddy joins this Deployment's own network, which is the only way it is reachable (and the
#     only network it is on). The Deployment shares nothing with the others on the box.
ssh "$BOX" "docker network connect oa-${ID}_default edge-caddy-1"
"$(dirname "$0")/proxy-key.sh" "$ID"   # attaches the LLM proxy too
ssh "$BOX" "sh -s -- $ID" < "$(dirname "$0")/isolation-check.sh" \
  || { echo "isolation check failed for $ID, not routing it" >&2; exit 1; }

# 5. Route the hostname: one site file, reload. A bad file leaves the running config in place.
ssh "$BOX" "printf '%s {\n    import openavisio %s\n}\n' $HOST $ID > /opt/edge/sites/$ID.caddy \
  && cd /opt/edge && docker compose -f docker-compose.edge.yml exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>&1 | tail -1"

# 6. HTTPS answers with a certificate for this name.
for _ in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}:%{ssl_verify_result}' "https://$HOST/" || true)
  [ "$code" = "307:0" ] && break
  sleep 5
done
[ "$code" = "307:0" ] || { echo "https://$HOST did not come up (got $code)" >&2; exit 1; }

echo
echo "Deployment $ID is up."
echo "Address : https://$HOST"
echo "Setup   : https://$HOST/setup#token=$BOOTSTRAP"
echo "Escrow  : $ESCROW_DIR/$ID.kek.age"
