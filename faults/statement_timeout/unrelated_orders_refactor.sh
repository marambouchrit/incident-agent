#!/usr/bin/env bash
# Unrelated refactor of the orders router (no behaviour change), deployed.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path

file = Path("app/routers/orders.py")
text = file.read_text(encoding="utf-8")
old_items = (
    '        "items": [\n'
    '            {"product_id": i.product_id, "quantity": i.quantity, "unit_price_cents": i.unit_price_cents}\n'
    "            for i in items\n"
    "        ]\n"
)
old_def = "def _item_count("
assert text.count(old_items) == 1 and text.count(old_def) == 1
text = text.replace(old_items, '        "items": [_item_dict(i) for i in items]\n')
text = text.replace(
    old_def,
    "def _item_dict(item: OrderItem) -> dict[str, Any]:\n"
    '    return {"product_id": item.product_id, "quantity": item.quantity, "unit_price_cents": item.unit_price_cents}\n'
    "\n\n" + old_def,
)
file.write_text(text, encoding="utf-8", newline="\n")
PY

commit_as "$TOMAS" "Extract order item serialization helper"
deploy api
