#!/usr/bin/env bash
# Makes the sales export load every order into memory, then deploys the worker.
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
    "worker/handlers/sales_export.py",
    """    query = (
        select(Order.created_at, Order.status, Order.total_cents)
        .where(Order.created_at >= since)
        .execution_options(yield_per=config.EXPORT_CHUNK_ROWS)
    )
    totals: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    rows = 0
    for created_at, status, total_cents in session.execute(query):
        bucket = totals[(created_at.strftime("%Y-%m-%dT%H:00Z"), status)]
        bucket[0] += 1
        bucket[1] += total_cents
        rows += 1
""",
    """    orders = session.scalars(select(Order).order_by(Order.created_at)).all()
    totals: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    all_time: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for order in orders:
        all_time[order.status][0] += 1
        all_time[order.status][1] += order.total_cents
        if order.created_at >= since:
            bucket = totals[(order.created_at.strftime("%Y-%m-%dT%H:00Z"), order.status)]
            bucket[0] += 1
            bucket[1] += order.total_cents
    rows = len(orders)
""",
)
edit(
    "worker/handlers/sales_export.py",
    "            writer.writerow([hour, status, count, total])\n",
    "            writer.writerow([hour, status, count, total])\n"
    "        for status, (count, total) in sorted(all_time.items()):\n"
    '            writer.writerow(["all_time", status, count, total])\n',
)
PY

commit_as "$PRIYA" "Include all-time totals in sales export"
mark_culprit
deploy worker
