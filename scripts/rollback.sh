#!/usr/bin/env bash
#
# Roll back to the previous version and check it works.
#
# Usage:
#   ./scripts/rollback.sh                 # go back to the previous release
#   ./scripts/rollback.sh apex-ops-api:0.1.0   # go back to a specific image

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

log()  { printf '\033[0;36m[rollback]\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

CURRENT_FILE=".deploy/current-release"
PREVIOUS_FILE=".deploy/previous-release"

command -v docker >/dev/null 2>&1 || die "docker is not installed"
docker compose version >/dev/null 2>&1 || die "docker compose v2 is required"

# --- Work out which image to go back to --------------------------------------
if [[ -n "${1:-}" ]]; then
  TARGET="$1"
  log "Rolling back to $TARGET"
else
  [[ -f "$PREVIOUS_FILE" ]] || die "No previous release was recorded, so there is nothing to roll back to"
  TARGET="$(cat "$PREVIOUS_FILE")"
  log "Rolling back to $TARGET"
fi

# --- Make sure the image is available ----------------------------------------
if ! docker image inspect "$TARGET" >/dev/null 2>&1; then
  warn "The image $TARGET is not on this machine. Trying to pull it."
  docker pull "$TARGET" || die "Could not get the image $TARGET"
fi

CURRENT="$(cat "$CURRENT_FILE" 2>/dev/null || echo 'unknown')"
log "Currently running $CURRENT"

# --- Swap the image ----------------------------------------------------------
log "Restarting the API with $TARGET"
IMAGE_TAG="$TARGET" docker compose up -d --no-deps --force-recreate api

# --- Wait for it to become healthy -------------------------------------------
log "Waiting for the API to become healthy"
status="starting"
for i in $(seq 1 30); do
  status="$(docker inspect --format='{{.State.Health.Status}}' apex-api 2>/dev/null || echo 'starting')"
  if [[ "$status" == "healthy" ]]; then
    log "API is healthy"
    break
  fi
  if [[ "$status" == "unhealthy" ]]; then
    warn "The rollback target is also unhealthy. Recent logs:"
    docker compose logs --tail=50 api
    die "Rollback did not fix the problem. Follow docs/runbook.md"
  fi
  sleep 2
done

if [[ "$status" != "healthy" ]]; then
  die "The API did not become healthy after the rollback (status: $status)"
fi

# --- Check the app can also reach the database -------------------------------
log "Checking the readiness endpoint"
if ! curl -fsS http://localhost:8000/readyz; then
  die "Readiness check failed after the rollback"
fi

# --- Swap the saved versions so a rollback can itself be rolled back --------
echo "$CURRENT" > "$PREVIOUS_FILE"
echo "$TARGET" > "$CURRENT_FILE"

log ""
log "Rolled back to $TARGET successfully"
