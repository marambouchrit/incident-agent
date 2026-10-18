#!/usr/bin/env bash
# Moves the order queries out of the router into a repository module, then deploys the api.
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
    "from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column\n",
    "from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship\n",
)
edit(
    "app/models.py",
    """    total_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderItem(Base):
""",
    """    total_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["OrderItem"]] = relationship()


class OrderItem(Base):
""",
)

router = Path("app/routers/orders.py")
old_router = '''from typing import Any

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
'''
assert router.read_text(encoding="utf-8") == old_router, "app/routers/orders.py is not at the expected version"
router.write_text(
    '''from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.repositories import orders as orders_repo

router = APIRouter()


@router.get("/orders")
def list_orders(
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return orders_repo.order_summaries(session, user_id)[:limit]


@router.get("/orders/{order_id:int}")
def get_order(order_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    order = orders_repo.get_order(session, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return orders_repo.order_dict(order) | {
        "items": [
            {"product_id": i.product_id, "quantity": i.quantity, "unit_price_cents": i.unit_price_cents}
            for i in order.items
        ]
    }
''',
    encoding="utf-8",
    newline="\n",
)

package = Path("app/repositories")
assert not package.exists(), "app/repositories already exists"
package.mkdir()
(package / "__init__.py").write_text("", encoding="utf-8", newline="\n")
(package / "orders.py").write_text(
    '''from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order


def order_dict(order: Order) -> dict[str, Any]:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "total_cents": order.total_cents,
        "created_at": order.created_at.isoformat(),
    }


def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)


def order_summaries(session: Session, user_id: int) -> list[dict[str, Any]]:
    query = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    orders = session.scalars(query).all()
    return [order_dict(o) | {"item_count": len(o.items)} for o in orders]
''',
    encoding="utf-8",
    newline="\n",
)
PY

commit_as "$TOMAS" "Move order queries into a repository module"
mark_culprit
deploy api
