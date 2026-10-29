#!/usr/bin/env bash
#
# Build and deploy a versioned image locally using Docker Compose.
#
# Usage:
#   ./scripts/deploy.sh [version]
#
# Example:
#   ./scripts/deploy.sh 0.1.0
#
# The version is saved to .deploy/current-release so rollback.sh knows which
# image to go back to. Safe to run more than once.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

log()  { printf '\033[0;36m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# --- Work out which version we are deploying ---------------------------------
if [[ -n "${1:-}" ]]; then
  VERSION="$1"
else
  VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' app/__init__.py)"
fi
[[ -n "$VERSION" ]] || die "Could not work out the version. Pass it in like: ./scripts/deploy.sh 0.1.0"

IMAGE_NAME="${IMAGE_NAME:-apex-ops-api}"
IMAGE_TAG="${IMAGE_NAME}:${VERSION}"

# --- Where we keep track of what is running ----------------------------------
mkdir -p .deploy
CURRENT_FILE=".deploy/current-release"
PREVIOUS_FILE=".deploy/previous-release"

command -v docker >/dev/null 2>&1 || die "docker is not installed"
docker compose version >/dev/null 2>&1 || die "docker compose v2 is required"

# --- Make sure we have a .env to read settings from -------------------------
if [[ ! -f .env ]]; then
  warn "No .env found - copying .env.example (local defaults only)"
  cp .env.example .env
fi

# --- Remember the current image so we can roll back to it --------------------
if [[ -f "$CURRENT_FILE" ]]; then
  CURRENT="$(cat "$CURRENT_FILE")"
  log "Currently running $CURRENT - saving it as the rollback target"
  echo "$CURRENT" > "$PREVIOUS_FILE"
fi

# --- Build -------------------------------------------------------------------
log "Building $IMAGE_TAG"
IMAGE_TAG="$IMAGE_TAG" docker compose build --pull api

# Save the new version before starting, so a failure is still traceable.
echo "$IMAGE_TAG" > "$CURRENT_FILE"

# --- Start -------------------------------------------------------------------
log "Starting the stack"
IMAGE_TAG="$IMAGE_TAG" docker compose up -d

# --- Wait for the container to report itself healthy -------------------------
log "Waiting for the API to become healthy"
status="starting"
for i in $(seq 1 30); do
  status="$(docker inspect --format='{{.State.Health.Status}}' apex-api 2>/dev/null || echo 'starting')"
  if [[ "$status" == "healthy" ]]; then
    log "API is healthy"
    break
  fi
  if [[ "$status" == "unhealthy" ]]; then
    warn "The API is unhealthy. Recent logs:"
    docker compose logs --tail=50 api
    die "Deploy failed. Roll back with: ./scripts/rollback.sh"
  fi
  sleep 2
done

if [[ "$status" != "healthy" ]]; then
  warn "The API never became healthy (status: $status). Recent logs:"
  docker compose logs --tail=50 api
  die "Deploy failed. Roll back with: ./scripts/rollback.sh"
fi

# --- Check the app can also reach the database -------------------------------
log "Checking the readiness endpoint"
if ! curl -fsS http://localhost:8000/readyz; then
  die "Readiness check failed. Roll back with: ./scripts/rollback.sh"
fi

log ""
log "Deployed $IMAGE_TAG successfully"
log "Rollback target: $(cat "$PREVIOUS_FILE" 2>/dev/null || echo 'none yet - this was the first release')"
