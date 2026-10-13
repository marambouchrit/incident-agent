#!/usr/bin/env bash
# A short burst of checkout traffic on top of the steady load.
set -euo pipefail
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps \
    -e LOADGEN_MIX=checkout -e LOADGEN_THREADS="${RUSH_THREADS:-60}" -e LOADGEN_RPS="${RUSH_RPS:-40}" \
    -e LOADGEN_DURATION_S="${RUSH_SECONDS:-20}" -e LOADGEN_SEED="$RANDOM" \
    loadgen python -m loadgen.run
