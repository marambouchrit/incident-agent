#!/usr/bin/env bash
# Clear jobs left unfinished by a crashing worker so the next run starts with an empty queue.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

psql_db "DELETE FROM jobs WHERE status <> 'done'"
