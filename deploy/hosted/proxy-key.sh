#!/usr/bin/env bash
# Give one hosted Deployment its own key for the LLM proxy (#375) and point its AI at the proxy.
# provision.sh calls it for a new Deployment; run it by hand to move an existing one over.
# Runs on the operator's machine, like provision.sh. The key reaches the box on stdin, not on the
# operator's command line; on the box it is briefly in sed's arguments, visible to root only.
#
#   deploy/hosted/proxy-key.sh <id>
#
# A second run replaces the Deployment's key: the old one stops working at once.
set -euo pipefail

ID=${1:?Deployment id}
CONF=${HOSTED_ENV:-$HOME/.config/openavisio/hosted.env}
BOX=$(sed -n 's/^BOX=//p' "$CONF"); : "${BOX:?}"
D=/opt/openavisio-$ID
F="-f docker-compose.prod.yml -f docker-compose.hosted.yml -f docker-compose.shared-box.yml"
KEY=$(openssl rand -hex 24)
HASH=$(printf '%s' "$KEY" | sha256sum | cut -d' ' -f1)

ssh "$BOX" "test -e $D/.env" || { echo "no Deployment $ID on $BOX" >&2; exit 1; }

# the proxy re-reads the file when it changes; only the hash is on the box outside the .env
ssh "$BOX" "umask 077; K=\$(docker volume inspect -f '{{.Mountpoint}}' edge_llm-proxy-data)/keys; \
  touch \$K; sed -i '/^$ID /d' \$K; echo '$ID $HASH' >> \$K"

ssh "$BOX" "cd $D && KEY=\$(cat) && sed -i \
  -e 's|^VLLM_URL=.*|VLLM_URL=http://edge-llm-proxy-1:8080/v1|' \
  -e 's|^VLLM_EMBED_URL=.*|VLLM_EMBED_URL=http://edge-llm-proxy-1:8080/v1|' \
  -e \"s|^VLLM_API_KEY=.*|VLLM_API_KEY=\$KEY|\" .env" <<<"$KEY"

ssh "$BOX" "docker network connect oa-${ID}_default edge-llm-proxy-1 2>/dev/null || true; \
  cd $D && docker compose $F up -d --no-build aiservice 2>&1 | tail -1"
echo "$ID now calls the AI through the proxy"
