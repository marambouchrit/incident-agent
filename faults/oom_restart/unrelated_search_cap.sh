#!/usr/bin/env bash
# Unrelated api change, deployed.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

sed -i 's#limit: int = Query(20, ge=1, le=50)#limit: int = Query(20, ge=1, le=30)#' app/routers/search.py
git diff --quiet && { echo "search.py was not changed" >&2; exit 1; }

commit_as "$LINA" "Cap product search results at 30"
deploy api
