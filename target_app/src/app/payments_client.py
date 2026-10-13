import logging

import httpx

from app import config

log = logging.getLogger("app.payments_client")


def charge(order_id: int, amount_cents: int) -> str:
    attempts = config.PAYMENTS_RETRIES + 1
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.post(
                f"{config.PAYMENTS_URL}/charge",
                json={"order_id": order_id, "amount_cents": amount_cents},
                timeout=config.PAYMENTS_TIMEOUT_S,
            )
            response.raise_for_status()
            return response.json()["ref"]
        except httpx.HTTPError as exc:
            if attempt == attempts:
                raise
            log.warning(
                "payment attempt failed, retrying",
                extra={"order_id": order_id, "attempt": attempt, "error": f"{type(exc).__name__}: {exc}"},
            )
    raise RuntimeError("unreachable")
