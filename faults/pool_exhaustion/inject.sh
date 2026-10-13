#!/usr/bin/env bash
# Shrinks the api's DB connection pool, then deploys the api.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

sed -i 's#^DB_POOL_SIZE=.*#DB_POOL_SIZE=2#' config/api.env
sed -i 's#^DB_MAX_OVERFLOW=.*#DB_MAX_OVERFLOW=0#' config/api.env
sed -i 's#^DB_POOL_TIMEOUT_S=.*#DB_POOL_TIMEOUT_S=1#' config/api.env

commit_as "$PRIYA" "Tune DB settings for staging parity"
mark_culprit
deploy api
