#!/usr/bin/env bash
#
# Verify that a fresh clone starts with one command and no credentials.
#
# This proves the claim the README makes: `docker compose up --build` brings the
# whole application up on a machine that has nothing installed but Docker, with
# no Meta, Google, or AI credentials configured. It clones the repository into a
# scratch directory so the working tree cannot influence the result, then checks
# the endpoints a user would actually hit first.
#
# Usage: scripts/fresh_clone_check.sh [repo-url]
# Defaults to the origin remote of the current checkout.

set -euo pipefail

REPO_URL="${1:-}"
WORK_DIR=""
WEB_URL="${WEB_URL:-http://127.0.0.1:5173}"
API_URL="${API_URL:-http://127.0.0.1:8000}"
# The API is containerised behind nginx, so the same-origin proxy path is the
# one a browser uses. Both are checked because they can fail independently.
PROXY_HEALTH_URL="${WEB_URL}/api/health"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-240}"

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[31mFAIL:\033[0m %s\n' "$*" >&2; exit 1; }

cleanup() {
    if [ -n "${WORK_DIR}" ] && [ -d "${WORK_DIR}" ]; then
        log "Tearing down the stack"
        (cd "${WORK_DIR}" && docker compose down -v --remove-orphans) || true
        rm -rf "${WORK_DIR}"
    fi
}
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || fail "docker is required but was not found on PATH"
docker compose version >/dev/null 2>&1 || fail "docker compose v2 is required but is unavailable"

if [ -z "${REPO_URL}" ]; then
    REPO_URL="$(git remote get-url origin 2>/dev/null || true)"
    [ -n "${REPO_URL}" ] || fail "no repository URL given and no origin remote to read one from"
fi

# A shallow clone keeps the check fast; the point is the build, not the history.
WORK_DIR="$(mktemp -d)"
log "Cloning ${REPO_URL} into ${WORK_DIR}"
git clone --depth 1 "${REPO_URL}" "${WORK_DIR}/repo"
cd "${WORK_DIR}/repo"

# A fresh clone must not need any credential file. The sandbox adapters and the
# deterministic AI provider are the defaults, so nothing is written here.
log "Building images (no .env, no credentials)"
docker compose build

log "Starting the stack"
docker compose up -d

log "Waiting up to ${MAX_WAIT_SECONDS}s for the services to become healthy"
waited=0
ready=0
while [ "${waited}" -lt "${MAX_WAIT_SECONDS}" ]; do
    # health and ready are the two endpoints the report calls out explicitly.
    if curl -fsS "${API_URL}/api/health" >/dev/null 2>&1 \
        && curl -fsS "${API_URL}/api/ready" >/dev/null 2>&1 \
        && curl -fsS "${PROXY_HEALTH_URL}" >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 3
    waited=$((waited + 3))
done

if [ "${ready}" -ne 1 ]; then
    log "Service logs:"
    docker compose logs --no-color || true
    fail "the stack did not become healthy within ${MAX_WAIT_SECONDS}s"
fi

log "Checking readiness reports sandbox integrations"
ready_body="$(curl -fsS "${API_URL}/api/ready")"
printf '    %s\n' "${ready_body}"

case "${ready_body}" in
    *'"integrations":"live"'*)
        fail "expected sandbox integrations but the stack reported live mode"
        ;;
esac

log "Checking the web app is served through nginx"
curl -fsS "${WEB_URL}/" >/dev/null || fail "the web root did not respond"

log "Confirming no credentials were required"
# A fresh clone has no .env; if the stack came up anyway, nothing external was needed.
if [ -f .env ]; then
    fail "a .env file exists in the clone, so this check did not run credential-free"
fi

log "Fresh clone started successfully with no external credentials"