#!/usr/bin/env bash
# Build the current commit and roll it out.
#   ./deploy.sh [--migrate] <service> [<service>...]
set -euo pipefail
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1

MIGRATE=0
if [ "${1:-}" = "--migrate" ]; then
    MIGRATE=1
    shift
fi
[ "$#" -gt 0 ] || { echo "usage: ./deploy.sh [--migrate] <service>..." >&2; exit 2; }

APP_VERSION="$(git rev-parse --short HEAD)"
export APP_VERSION

docker compose build api
if [ "$MIGRATE" = 1 ]; then
    docker compose run --rm --no-deps api alembic upgrade head
fi
docker compose up -d --no-deps "$@"
