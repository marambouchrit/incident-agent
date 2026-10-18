#!/usr/bin/env bash
# Product search ranks matches by units sold over the last 30 days, deployed.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"expected exactly one match in {path}: {old!r}"
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("app/routers/search.py", "from typing import Any\n", "from datetime import datetime, timedelta, timezone\nfrom typing import Any\n")
edit("app/routers/search.py", "from sqlalchemy import select\n", "from sqlalchemy import func, select\n")
edit("app/routers/search.py", "from app.models import Product\n", "from app.models import Order, OrderItem, Product\n")
edit(
    "app/routers/search.py",
    '    query = select(Product).where(Product.name.ilike(f"%{q}%")).order_by(Product.name).limit(limit)\n',
    "    since = datetime.now(timezone.utc) - timedelta(days=30)\n"
    "    units_sold = (\n"
    '        select(OrderItem.product_id, func.sum(OrderItem.quantity).label("units"))\n'
    "        .join(Order, Order.id == OrderItem.order_id)\n"
    '        .where(Order.status == "paid", Order.created_at >= since)\n'
    "        .group_by(OrderItem.product_id)\n"
    "        .subquery()\n"
    "    )\n"
    "    query = (\n"
    "        select(Product)\n"
    "        .outerjoin(units_sold, units_sold.c.product_id == Product.id)\n"
    '        .where(Product.name.ilike(f"%{q}%"))\n'
    "        .order_by(func.coalesce(units_sold.c.units, 0).desc(), Product.name)\n"
    "        .limit(limit)\n"
    "    )\n",
)
PY

commit_as "$LINA" "Rank product search results by popularity"
deploy api
