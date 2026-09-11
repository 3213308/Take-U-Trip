# app/api/routes/itinerary.py
"""行程查询 API"""

from fastapi import APIRouter
from app.memory.store import get_memory_store

router = APIRouter(prefix="/api/itinerary", tags=["itinerary"])

USER_ID = "default"


@router.get("/latest")
def latest_itinerary():
    store = get_memory_store()
    trips = store.get_recent_itineraries(USER_ID, limit=1)
    if not trips:
        return {"itinerary": None}
    return {"itinerary": trips[0]}


@router.get("/history")
def itinerary_history(limit: int = 10):
    store = get_memory_store()
    trips = store.get_recent_itineraries(USER_ID, limit=limit)
    return {"items": trips}
