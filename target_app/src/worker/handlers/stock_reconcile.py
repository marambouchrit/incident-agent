import logging
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app import config
from app.models import Inventory

KIND = "stock_reconcile"
INTERVAL_S = config.RECONCILE_INTERVAL_S
LOW_WATER = 1000
RESTOCK_TO = 100000
log = logging.getLogger("worker.jobs")


def handle(session: Session, payload: dict[str, Any]) -> None:
    result = session.execute(update(Inventory).where(Inventory.quantity < LOW_WATER).values(quantity=RESTOCK_TO))
    log.info("stock reconciled", extra={"restocked_products": result.rowcount})
