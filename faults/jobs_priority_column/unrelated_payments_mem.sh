#!/usr/bin/env bash
# Unrelated memory limit change for the payments stub, deployed.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path

file = Path("docker-compose.yml")
text = file.read_text(encoding="utf-8")
old = '    command: ["python", "-m", "payments_stub.main"]\n    mem_limit: 64m\n'
assert text.count(old) == 1, "expected exactly one match in docker-compose.yml"
file.write_text(text.replace(old, old.replace("64m", "128m")), encoding="utf-8", newline="\n")
PY

commit_as "$LINA" "Give payment stub more headroom"
deploy payments
