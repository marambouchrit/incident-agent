import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.models import Order, User

KIND = "order_confirmation"
log = logging.getLogger("worker.jobs")


def handle(session: Session, payload: dict[str, Any]) -> None:
    order = session.get(Order, payload["order_id"])
    if order is None:
        raise LookupError(f"order {payload['order_id']} not found")
    user = session.get(User, order.user_id)
    time.sleep(0.02)  # mail gateway round trip
    log.info("order confirmation sent", extra={"order_id": order.id, "user_id": user.id if user else None})
