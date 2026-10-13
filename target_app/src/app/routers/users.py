from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User

router = APIRouter()


class UserIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    name: str = Field(min_length=1, max_length=120)


def _to_dict(user: User) -> dict[str, Any]:
    return {"id": user.id, "email": user.email, "name": user.name, "created_at": user.created_at.isoformat()}


@router.post("/users", status_code=201)
def create_user(body: UserIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    user = User(email=body.email, name=body.name)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="email already registered")
    session.refresh(user)
    return _to_dict(user)


@router.get("/users/{user_id:int}")
def get_user(user_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return _to_dict(user)
