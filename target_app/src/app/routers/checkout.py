import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, payments_client
from app.db import get_session
from app.models import Inventory, Job, Order, OrderItem, Payment, Product, User

router = APIRouter()
log = logging.getLogger("app.checkout")


class Item(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=20)


class CheckoutIn(BaseModel):
    user_id: int
    items: list[Item] = Field(min_length=1, max_length=10)
    discount_code: str | None = None


@router.post("/checkout", status_code=201)
def checkout(body: CheckoutIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    if session.get(User, body.user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")

    wanted: dict[int, int] = {}
    for item in body.items:
        wanted[item.product_id] = wanted.get(item.product_id, 0) + item.quantity
    ids = sorted(wanted)

    products = {p.id: p for p in session.scalars(select(Product).where(Product.id.in_(ids)))}
    if len(products) != len(ids):
        raise HTTPException(status_code=404, detail="product not found")

    stock_query = select(Inventory).where(Inventory.product_id.in_(ids)).order_by(Inventory.product_id)
    stock = {s.product_id: s for s in session.scalars(stock_query.with_for_update())}
    for product_id, quantity in wanted.items():
        if product_id not in stock or stock[product_id].quantity < quantity:
            raise HTTPException(status_code=409, detail="insufficient stock")
        stock[product_id].quantity -= quantity

    total = sum(products[pid].price_cents * qty for pid, qty in wanted.items())
    if config.FEATURE_DISCOUNTS and body.discount_code:
        total = int(total * 0.9)

    order = Order(user_id=body.user_id, status="pending", total_cents=total)
    session.add(order)
    session.flush()
    for product_id, quantity in wanted.items():
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=product_id,
                quantity=quantity,
                unit_price_cents=products[product_id].price_cents,
            )
        )

    provider_ref = payments_client.charge(order.id, total)
    session.add(Payment(order_id=order.id, provider_ref=provider_ref, amount_cents=total, status="captured"))
    order.status = "paid"
    session.add(Job(kind="order_confirmation", payload={"order_id": order.id}))
    session.commit()

    log.info("order placed", extra={"order_id": order.id, "total_cents": total})
    return {"order_id": order.id, "status": order.status, "total_cents": total}
