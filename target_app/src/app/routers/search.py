from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Product

router = APIRouter()


@router.get("/products/search")
def search_products(
    q: str = Query(min_length=2, max_length=60),
    limit: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(Product).where(Product.name.ilike(f"%{q}%")).order_by(Product.name).limit(limit)
    return [
        {"id": p.id, "name": p.name, "category": p.category, "price_cents": p.price_cents}
        for p in session.scalars(query)
    ]
