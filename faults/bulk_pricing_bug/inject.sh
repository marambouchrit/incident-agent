#!/usr/bin/env bash
# Adds tiered pricing for carts with several products, then deploys the api.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"expected exactly one match in {path}"
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


pricing = Path("app/pricing.py")
assert not pricing.exists()
pricing.write_text(
    '''from decimal import ROUND_HALF_UP, Decimal

BULK_TIERS = ((6, 0.10), (3, 0.05))


def bulk_discount_cents(lines: list[tuple[int, int]]) -> int:
    """Discount for carts with several different products. lines: (unit_price_cents, quantity)."""
    for min_lines, rate in BULK_TIERS:
        if len(lines) >= min_lines:
            subtotal = Decimal(sum(price * quantity for price, quantity in lines))
            return int((subtotal * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return 0
''',
    encoding="utf-8",
    newline="\n",
)

edit(
    "app/routers/checkout.py",
    "from app import config, payments_client\n",
    "from app import config, payments_client, pricing\n",
)
edit(
    "app/routers/checkout.py",
    "    total = sum(products[pid].price_cents * qty for pid, qty in wanted.items())\n",
    "    total = sum(products[pid].price_cents * qty for pid, qty in wanted.items())\n"
    "    total -= pricing.bulk_discount_cents([(products[pid].price_cents, qty) for pid, qty in wanted.items()])\n",
)
PY

commit_as "$LINA" "Add bulk pricing for multi-item carts"
mark_culprit
deploy api
