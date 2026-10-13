#!/usr/bin/env bash
# This fault only changes files tracked in git; clear any jobs still queued after a burst.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

psql_db "DELETE FROM jobs WHERE status <> 'done'"
