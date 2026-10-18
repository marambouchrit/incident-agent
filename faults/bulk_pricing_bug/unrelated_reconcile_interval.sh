#!/usr/bin/env bash
# Unrelated worker settings change, deployed to the worker only.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path

file = Path("config/worker.env")
text = file.read_text(encoding="utf-8")
old = "RECONCILE_INTERVAL_S=300\n"
assert text.count(old) == 1, "expected RECONCILE_INTERVAL_S=300 in config/worker.env"
file.write_text(text.replace(old, "RECONCILE_INTERVAL_S=600\n"), encoding="utf-8", newline="\n")
PY

commit_as "$TOMAS" "Run stock reconciliation every 10 minutes"
deploy worker
