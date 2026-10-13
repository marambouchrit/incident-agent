import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.db import get_session
from app.models import Product

router = APIRouter()

_cache: dict[tuple[str | None, int, int], tuple[float, list[dict[str, Any]]]] = {}


def _to_dict(product: Product) -> dict[str, Any]:
    return {"id": product.id, "name": product.name, "category": product.category, "price_cents": product.price_cents}


@router.get("/products")
def list_products(
    category: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    key = (category, page, page_size)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < config.CATALOG_CACHE_TTL_S:
        return cached[1]
    query = select(Product).order_by(Product.id).offset((page - 1) * page_size).limit(page_size)
    if category:
        query = query.where(Product.category == category)
    result = [_to_dict(p) for p in session.scalars(query)]
    _cache[key] = (time.monotonic(), result)
    return result


@router.get("/products/{product_id:int}")
def get_product(product_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return _to_dict(product)
