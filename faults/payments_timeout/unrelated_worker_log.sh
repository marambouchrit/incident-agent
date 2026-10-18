#!/usr/bin/env bash
# Unrelated worker change (one more field on a log line), deployed: restarts the worker early.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path

file = Path("worker/handlers/order_confirmation.py")
text = file.read_text(encoding="utf-8")
old = '    log.info("order confirmation sent", extra={"order_id": order.id, "user_id": user.id if user else None})\n'
assert text.count(old) == 1, "order_confirmation.py does not match"
text = text.replace(
    old,
    "    log.info(\n"
    '        "order confirmation sent",\n'
    '        extra={"order_id": order.id, "user_id": user.id if user else None, "total_cents": order.total_cents},\n'
    "    )\n",
)
file.write_text(text, encoding="utf-8", newline="\n")
PY

commit_as "$TOMAS" "Include order total in confirmation log"
deploy worker
