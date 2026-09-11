# app/api/routes/__init__.py
from app.api.routes.chat import router as chat_router
from app.api.routes.wishlist import router as wishlist_router
from app.api.routes.itinerary import router as itinerary_router

__all__ = ["chat_router", "wishlist_router", "itinerary_router"]
