#!/usr/bin/env bash
# Unrelated refactor of the request logging middleware (no behaviour change), deployed.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path

file = Path("app/middleware.py")
text = file.read_text(encoding="utf-8")
old_fields = '    fields = {"method": request.method, "path": request.url.path}\n'
old_def = "async def request_logging("
assert text.count(old_fields) == 1 and text.count(old_def) == 1
text = text.replace(old_fields, "    fields = _request_fields(request)\n")
text = text.replace(
    old_def,
    "def _request_fields(request: Request) -> dict[str, object]:\n"
    '    return {"method": request.method, "path": request.url.path}\n\n\n' + old_def,
)
file.write_text(text, encoding="utf-8", newline="\n")
PY

commit_as "$TOMAS" "Refactor request logging fields"
deploy api
