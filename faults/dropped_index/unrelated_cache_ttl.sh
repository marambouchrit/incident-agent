#!/usr/bin/env bash
# Unrelated api settings change, deployed.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

sed -i 's#^CATALOG_CACHE_TTL_S=.*#CATALOG_CACHE_TTL_S=120#' config/api.env

commit_as "$LINA" "Raise catalog cache TTL to 120s"
deploy api
