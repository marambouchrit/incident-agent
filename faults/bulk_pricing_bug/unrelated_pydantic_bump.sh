#!/usr/bin/env bash
# Unrelated patch-level dependency bump (pydantic-core stays 2.27.2), deployed to the api.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path

file = Path("requirements.txt")
text = file.read_text(encoding="utf-8")
old = "pydantic==2.10.4\n"
assert text.count(old) == 1, "expected pydantic==2.10.4 in requirements.txt"
file.write_text(text.replace(old, "pydantic==2.10.6\n"), encoding="utf-8", newline="\n")
PY

commit_as "$TOMAS" "Bump pydantic to 2.10.6"
deploy api
