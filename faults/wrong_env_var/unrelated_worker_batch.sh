#!/usr/bin/env bash
# Unrelated settings change on the worker, deployed.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

sed -i 's#^WORKER_BATCH_SIZE=.*#WORKER_BATCH_SIZE=20#' config/worker.env

commit_as "$PRIYA" "Increase worker batch size to 20"
deploy worker
