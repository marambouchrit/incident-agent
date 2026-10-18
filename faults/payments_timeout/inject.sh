#!/usr/bin/env bash
# Tidies the payments client (harmless) and, in the same commit, sets the payments timeout below the
# provider's normal latency (20-80 ms in payments_stub) with no retries. Deploys the api.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"expected exactly one match in {path}: {old!r}"
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit(
    "app/payments_client.py",
    'log = logging.getLogger("app.payments_client")\n',
    'log = logging.getLogger("app.payments_client")\n\nHEADERS = {"User-Agent": f"shopline-api/{config.APP_VERSION}"}\n',
)
edit(
    "app/payments_client.py",
    """    attempts = config.PAYMENTS_RETRIES + 1
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.post(
                f"{config.PAYMENTS_URL}/charge",
                json={"order_id": order_id, "amount_cents": amount_cents},
                timeout=config.PAYMENTS_TIMEOUT_S,
            )
""",
    """    url = f"{config.PAYMENTS_URL}/charge"
    body = {"order_id": order_id, "amount_cents": amount_cents}
    attempts = config.PAYMENTS_RETRIES + 1
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.post(url, json=body, headers=HEADERS, timeout=config.PAYMENTS_TIMEOUT_S)
""",
)
edit("config/api.env", "PAYMENTS_TIMEOUT_S=3\n", "PAYMENTS_TIMEOUT_S=0.07\n")
edit("config/api.env", "PAYMENTS_RETRIES=2\n", "PAYMENTS_RETRIES=0\n")
PY

commit_as "$LINA" "Tune HTTP client defaults for payments"
mark_culprit
deploy api
