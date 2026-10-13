#!/usr/bin/env bash
# Adds orders.discount_code to the code only, then deploys the api without a schema update.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"expected exactly one match in {path}"
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit(
    "app/models.py",
    "    total_cents: Mapped[int] = mapped_column(Integer)\n",
    "    total_cents: Mapped[int] = mapped_column(Integer)\n"
    "    discount_code: Mapped[str | None] = mapped_column(String(40), nullable=True)\n",
)
edit(
    "app/routers/checkout.py",
    '    order = Order(user_id=body.user_id, status="pending", total_cents=total)\n',
    "    discount_code = body.discount_code if config.FEATURE_DISCOUNTS else None\n"
    '    order = Order(user_id=body.user_id, status="pending", total_cents=total, discount_code=discount_code)\n',
)
edit(
    "app/routers/orders.py",
    '        "total_cents": order.total_cents,\n',
    '        "total_cents": order.total_cents,\n        "discount_code": order.discount_code,\n',
)
PY

commit_as "$TOMAS" "Add discount codes to checkout"
mark_culprit
deploy api
