#!/usr/bin/env bash
# Bring the payment provider back up. A no-op when it is already running.
set -euo pipefail
export MSYS_NO_PATHCONV=1
export APP_VERSION="${APP_VERSION:-$(git rev-parse --short HEAD)}"

docker compose up -d --no-deps payments
