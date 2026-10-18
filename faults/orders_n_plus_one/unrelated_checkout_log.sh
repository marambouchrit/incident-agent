#!/usr/bin/env bash
# Unrelated api change on the checkout path, deployed.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path

file = Path("app/routers/checkout.py")
text = file.read_text(encoding="utf-8")
old = '    log.info("order placed", extra={"order_id": order.id, "total_cents": total})\n'
assert text.count(old) == 1, "expected exactly one match in app/routers/checkout.py"
new = (
    '    log.info(\n'
    '        "order placed",\n'
    '        extra={"order_id": order.id, "total_cents": total, "item_count": len(wanted)},\n'
    '    )\n'
)
file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
PY

commit_as "$LINA" "Log item count when an order is placed"
deploy api
