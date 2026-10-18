#!/usr/bin/env bash
# Remove queued/failed jobs (including the confirmation jobs for missing orders). Safe on a healthy shop.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

psql_db "DELETE FROM jobs WHERE status <> 'done'"
