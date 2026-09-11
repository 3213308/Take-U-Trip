# app/api/routes/wishlist.py
"""愿望清单 CRUD API"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.memory.store import get_memory_store

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])

USER_ID = "default"  # MVP 阶段单用户


class WishCreate(BaseModel):
    name: str
    category: str = ""
    city: str = ""
    note: str = ""


class WishUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    city: str | None = None
    note: str | None = None
    checked: bool | None = None
    sort_order: int | None = None


@router.get("")
def list_wishes():
    store = get_memory_store()
    return {"items": store.get_wishlist(USER_ID)}


@router.post("")
def add_wish(body: WishCreate):
    store = get_memory_store()
    wish_id = store.add_wish(USER_ID, body.name, body.category, body.note, body.city)
    return {"id": wish_id}


@router.put("/{wish_id}")
def update_wish(wish_id: int, body: WishUpdate):
    store = get_memory_store()
    store.update_wish(USER_ID, wish_id, **body.model_dump(exclude_none=True))
    return {"ok": True}


@router.delete("/{wish_id}")
def delete_wish(wish_id: int):
    store = get_memory_store()
    store.delete_wish(USER_ID, wish_id)
    return {"ok": True}
