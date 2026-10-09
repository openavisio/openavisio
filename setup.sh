#!/usr/bin/env bash
# OpenAvisio first-run setup script
# Generates .env, optionally starts the stack.
# Usage: ./setup.sh [--non-interactive] [--force] [--start] [--env-file=.env]

set -euo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
if [ -t 1 ] && command -v tput &>/dev/null; then
  BOLD=$(tput bold); RESET=$(tput sgr0)
  CYAN=$(tput setaf 6); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3); RED=$(tput setaf 1)
else
  BOLD=''; RESET=''; CYAN=''; GREEN=''; YELLOW=''; RED=''
fi

info()    { echo "${CYAN}  ➜  ${RESET}$*"; }
success() { echo "${GREEN}  ✓  ${RESET}$*"; }
warn()    { echo "${YELLOW}  ⚠  ${RESET}$*"; }
error()   { echo "${RED}  ✗  ${RESET}$*" >&2; }
header()  { echo; echo "${BOLD}${CYAN}━━━  $*  ━━━${RESET}"; echo; }

# ── parse flags ───────────────────────────────────────────────────────────────
NON_INTERACTIVE=false
FORCE=false
START=false
ENV_FILE=".env"

for arg in "$@"; do
  case "$arg" in
    --non-interactive) NON_INTERACTIVE=true ;;
    --force)           FORCE=true ;;
    --start)           START=true ;;
    --env-file=*)      ENV_FILE="${arg#*=}" ;;
    -h|--help)
      echo "Usage: $0 [--non-interactive] [--force] [--start] [--env-file=.env]"
      exit 0 ;;
  esac
done

# ── helpers ───────────────────────────────────────────────────────────────────
gen_secret() { openssl rand -hex 32; }

# Read a value: existing file value > env var > prompt > default
ask() {
  local key="$1" prompt="$2" default="$3" secret="${4:-false}"
  local current; current=$(get_env "$key")
  [ -n "$current" ] && ! $FORCE && { echo "$current"; return; }
  [ -n "${!key:-}" ] && ! $FORCE && { echo "${!key}"; return; }  # env var
  if $NON_INTERACTIVE; then
    [ -n "$default" ] && { echo "$default"; return; }
    $secret && return  # empty → caller auto-generates
    error "Missing required value for $key in non-interactive mode"; exit 1
  fi
  local value
  if $secret; then
    read -rsp "  ${prompt} [leave blank to auto-generate]: " value; echo
  else
    [ -n "$default" ] && read -rp "  ${prompt} [${default}]: " value \
      || read -rp "  ${prompt}: " value
    [ -z "$value" ] && value="$default"
  fi
  echo "$value"
}

ask_choice() {
  local key="$1" prompt="$2"; shift 2; local options=("$@")
  local current; current=$(get_env "$key")
  [ -n "$current" ] && ! $FORCE && { echo "$current"; return; }
  if $NON_INTERACTIVE; then echo "${options[0]}"; return; fi
  echo "  $prompt" >&2
  for i in "${!options[@]}"; do echo "    $((i+1)). ${options[$i]}" >&2; done
  local choice
  while true; do
    read -rp "  Choice (number or name) [1]: " choice
    [ -z "$choice" ] && choice=1
    # Accept numeric index
    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#options[@]}" ]; then
      echo "${options[$((choice-1))]}"; return
    fi
    # Accept option name directly
    for opt in "${options[@]}"; do
      [ "$choice" = "$opt" ] && { echo "$opt"; return; }
    done
    warn "Invalid choice — enter a number (1-${#options[@]}) or a name ($(IFS=, ; echo "${options[*]}"))" >&2
  done
}

get_env() {
  [ -f "$ENV_FILE" ] && grep -m1 "^${1}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' || true
}

set_env() {
  local key="$1" value="$2"
  if [ -f "$ENV_FILE" ] && grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    # Update existing key (portable sed)
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "$ENV_FILE" && rm -f "${ENV_FILE}.bak"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

# ── prerequisites ─────────────────────────────────────────────────────────────
header "Prerequisites"
for cmd in docker openssl; do
  if command -v "$cmd" &>/dev/null; then
    success "$cmd found"
  else
    error "$cmd is required but not found. Please install it first."; exit 1
  fi
done
if docker compose version &>/dev/null 2>&1; then
  success "docker compose found"
else
  error "docker compose plugin not found. Please install Docker Desktop or docker-compose-plugin."; exit 1
fi

# ── secrets ───────────────────────────────────────────────────────────────────
header "Secrets"

APP_SECRET_VAL=$(ask APP_SECRET "APP_SECRET" "" true)
[ -z "$APP_SECRET_VAL" ] && APP_SECRET_VAL=$(gen_secret) && info "Generated APP_SECRET"
set_env APP_SECRET "$APP_SECRET_VAL"

NEXTAUTH_SECRET_VAL=$(ask NEXTAUTH_SECRET "NEXTAUTH_SECRET" "" true)
[ -z "$NEXTAUTH_SECRET_VAL" ] && NEXTAUTH_SECRET_VAL=$(gen_secret) && info "Generated NEXTAUTH_SECRET"
set_env NEXTAUTH_SECRET "$NEXTAUTH_SECRET_VAL"

# ── database ──────────────────────────────────────────────────────────────────
header "Database"

POSTGRES_USER_VAL=$(ask POSTGRES_USER "PostgreSQL username" "openavisio")
set_env POSTGRES_USER "$POSTGRES_USER_VAL"

POSTGRES_PASSWORD_VAL=$(ask POSTGRES_PASSWORD "PostgreSQL password" "" true)
[ -z "$POSTGRES_PASSWORD_VAL" ] && POSTGRES_PASSWORD_VAL=$(gen_secret) && info "Generated POSTGRES_PASSWORD"
set_env POSTGRES_PASSWORD "$POSTGRES_PASSWORD_VAL"

POSTGRES_DB_VAL=$(ask POSTGRES_DB "Database name" "vaultdb")
set_env POSTGRES_DB "$POSTGRES_DB_VAL"

# Document envelope-encryption KEK (ADR-022, mandatory) — base64, 32 bytes
DOC_KEY_VAL=$(ask DOCUMENT_ENCRYPTION_KEY "DOCUMENT_ENCRYPTION_KEY" "" true)
[ -z "$DOC_KEY_VAL" ] && DOC_KEY_VAL=$(openssl rand -base64 32) && info "Generated DOCUMENT_ENCRYPTION_KEY"
set_env DOCUMENT_ENCRYPTION_KEY "$DOC_KEY_VAL"

# One-time token gating the first-run setup wizard (POST /organization/init)
BOOTSTRAP_TOKEN_VAL=$(ask BOOTSTRAP_TOKEN "BOOTSTRAP_TOKEN" "" true)
[ -z "$BOOTSTRAP_TOKEN_VAL" ] && BOOTSTRAP_TOKEN_VAL=$(gen_secret) && info "Generated BOOTSTRAP_TOKEN"
set_env BOOTSTRAP_TOKEN "$BOOTSTRAP_TOKEN_VAL"

# Shared secret for backend→aiservice calls (#46)
AISERVICE_TOKEN_VAL=$(ask AISERVICE_TOKEN "AISERVICE_TOKEN" "" true)
[ -z "$AISERVICE_TOKEN_VAL" ] && AISERVICE_TOKEN_VAL=$(gen_secret) && info "Generated AISERVICE_TOKEN"
set_env AISERVICE_TOKEN "$AISERVICE_TOKEN_VAL"

# ── domain ────────────────────────────────────────────────────────────────────
header "Domain"

DOMAIN_VAL=$(ask DOMAIN "Your domain or IP (e.g. health.example.com or 192.168.1.50)" "")
if [ -z "$DOMAIN_VAL" ]; then
  warn "No domain set — using localhost. Change DOMAIN in $ENV_FILE before production deployment."
  DOMAIN_VAL="localhost"
fi
set_env DOMAIN "$DOMAIN_VAL"

# Bare IP addresses or localhost → HTTP only (Caddy won't get a Let's Encrypt cert)
if [[ "$DOMAIN_VAL" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || [ "$DOMAIN_VAL" = "localhost" ]; then
  SCHEME="http"
  warn "IP address or localhost detected — using HTTP (no TLS). NEXTAUTH_URL and CORS_ORIGINS set to http://."
else
  SCHEME="https"
fi
set_env NEXTAUTH_URL "${SCHEME}://${DOMAIN_VAL}"
set_env API_URL "http://backend:8000"
set_env CORS_ORIGINS "${SCHEME}://${DOMAIN_VAL}"

# Passkeys (WebAuthn) — RP ID must match the domain users sign in on
set_env WEBAUTHN_RP_ID "$DOMAIN_VAL"
set_env WEBAUTHN_RP_NAME "OpenAvisio"
set_env WEBAUTHN_ORIGIN "${SCHEME}://${DOMAIN_VAL}"

# ── AI backend ────────────────────────────────────────────────────────────────
header "AI Backend"

echo "  How should OpenAvisio run AI (document extraction, chat assistant)?"
echo ""
echo "    1. ollama   — Ollama instance, local or anywhere on the network"
echo "                  (recommended for homelab/self-hosted)."
echo "                  Models are managed in Ollama; you pick them in the admin UI."
echo ""
echo "    2. mock     — Canned responses, no GPU needed. Good for testing the UI"
echo "                  and verifying the stack works before connecting a real model."
echo ""
echo "    3. vllm     — High-throughput vLLM server (advanced, for multi-user orgs)."
echo ""
AI_BACKEND_VAL=$(ask_choice AI_BACKEND "Your choice:" "ollama" "mock" "vllm")
set_env AI_BACKEND "$AI_BACKEND_VAL"

case "$AI_BACKEND_VAL" in
  ollama)
    OLLAMA_URL_VAL=$(ask OLLAMA_URL "Ollama URL (local or network, e.g. http://192.168.1.10:11434)" "http://localhost:11434")
    set_env OLLAMA_URL "$OLLAMA_URL_VAL"
    info "Model selection (extract, classify, chat, vision) is configured in the admin UI after first login."
    info "Pull models in Ollama first — recommended: medgemma:27b, gemma4:31b, qwen3-embedding:4b, glm-ocr"
    ;;
  vllm)
    VLLM_URL_VAL=$(ask VLLM_URL "vLLM endpoint URL" "http://vllm:8000")
    set_env VLLM_URL "$VLLM_URL_VAL"
    VLLM_MODEL_VAL=$(ask VLLM_MODEL "vLLM model name" "")
    set_env VLLM_MODEL "$VLLM_MODEL_VAL"
    ;;
  mock)
    info "Using mock AI backend — no configuration needed"
    ;;
esac

# ── summary ───────────────────────────────────────────────────────────────────
header "Done"
success "Configuration written to ${ENV_FILE}"
echo
echo "  Next steps:"
echo "  1. Review ${ENV_FILE} and adjust any values"
echo "  2. Start the stack:"
echo "     ${BOLD}docker compose up -d${RESET}"
echo "  3. Open https://${DOMAIN_VAL} in your browser to complete setup"
echo
echo "  ${BOLD}Setup wizard token${RESET} (paste into the first-run wizard to create the admin):"
echo "     ${BOLD}${BOOTSTRAP_TOKEN_VAL}${RESET}"
echo "  Keep it private; it is only needed once, until the admin account exists."
echo

if $START; then
  header "Starting stack"
  # Root compose.yml (includes deploy/docker-compose.prod.yml) — keeps the
  # project dir at repo root so docker compose picks up the generated .env.
  docker compose up -d
  success "Stack started. Visit https://${DOMAIN_VAL} to finish setup."
fi
