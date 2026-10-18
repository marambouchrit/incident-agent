#!/usr/bin/env bash
# Unrelated dependency commit (dev tooling only, not part of the image install), not deployed.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

[ ! -e requirements-dev.txt ] || { echo "requirements-dev.txt already exists" >&2; exit 1; }
cat > requirements-dev.txt <<'REQ'
-r requirements.txt
pytest==8.3.4
ruff==0.8.4
REQ

commit_as "$PRIYA" "Add dev requirements for tests and linting"
