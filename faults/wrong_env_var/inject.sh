#!/usr/bin/env bash
# Points the api at a payments port nothing listens on, then deploys the api.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

sed -i 's#^PAYMENTS_URL=.*#PAYMENTS_URL=http://payments:8443#' config/api.env
sed -i 's#^PAYMENTS_TIMEOUT_S=.*#PAYMENTS_TIMEOUT_S=5#' config/api.env

commit_as "$TOMAS" "Align payments client settings with provider guide"
mark_culprit
deploy api
