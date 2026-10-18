#!/usr/bin/env bash
# Unrelated api config change (catalog cache TTL), deployed a few minutes before the outage.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path

file = Path("config/api.env")
text = file.read_text(encoding="utf-8")
old = "CATALOG_CACHE_TTL_S=30\n"
assert text.count(old) == 1, "expected exactly one CATALOG_CACHE_TTL_S=30 line in config/api.env"
file.write_text(text.replace(old, "CATALOG_CACHE_TTL_S=10\n"), encoding="utf-8", newline="\n")
PY

commit_as "$LINA" "Refresh catalog cache more often"
deploy api
