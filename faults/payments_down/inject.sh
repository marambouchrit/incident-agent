#!/usr/bin/env bash
# The payment provider goes down and stays down. No commit, no deploy, api config untouched.
# A killed container counts as manually stopped, so restart: unless-stopped does not bring it back;
# the stop afterwards is a no-op that makes sure of it.
set -euo pipefail
export MSYS_NO_PATHCONV=1

docker compose kill payments
docker compose stop payments
