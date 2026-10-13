from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Order, OrderItem

router = APIRouter()


def _to_dict(order: Order) -> dict[str, Any]:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "total_cents": order.total_cents,
        "created_at": order.created_at.isoformat(),
    }


def _item_count(session: Session, order_id: int) -> int:
    query = select(func.count()).select_from(OrderItem).where(OrderItem.order_id == order_id)
    return session.scalar(query) or 0


@router.get("/orders")
def list_orders(
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit)
    orders = session.scalars(query).all()
    return [_to_dict(o) | {"item_count": _item_count(session, o.id)} for o in orders]


@router.get("/orders/{order_id:int}")
def get_order(order_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    items = session.scalars(select(OrderItem).where(OrderItem.order_id == order_id))
    return _to_dict(order) | {
        "items": [
            {"product_id": i.product_id, "quantity": i.quantity, "unit_price_cents": i.unit_price_cents}
            for i in items
        ]
    }
