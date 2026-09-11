# app/memory/store.py
"""长期记忆存储 — SQLAlchemy ORM 版

三张表：profiles / itineraries / wishlist
接口与旧版兼容，调用方无需改动。
"""

import json
import logging
from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import Profile, Itinerary as ItineraryModel, Wishlist

logger = logging.getLogger(__name__)


class MemoryStore:

    # ===== 用户画像 =====

    def get_profile(self, user_id: str) -> dict:
        with SessionLocal() as db:
            row = db.get(Profile, user_id)
            return json.loads(row.data) if row else {}

    def save_profile(self, user_id: str, profile: dict):
        profile["updated_at"] = datetime.now().isoformat()
        with SessionLocal() as db:
            row = db.get(Profile, user_id)
            if row:
                row.data = json.dumps(profile, ensure_ascii=False)
                row.updated_at = datetime.now()
            else:
                db.add(Profile(
                    user_id=user_id,
                    data=json.dumps(profile, ensure_ascii=False),
                    updated_at=datetime.now(),
                ))
            db.commit()
        logger.info("用户画像已更新: %s", user_id)

    def merge_profile(self, user_id: str, new_preferences: dict):
        existing = self.get_profile(user_id)
        for key, value in new_preferences.items():
            if isinstance(value, list) and key in existing:
                merged = list(dict.fromkeys(existing[key] + value))
                existing[key] = merged
            elif value:
                existing[key] = value
        self.save_profile(user_id, existing)

    # ===== 历史行程 =====

    def get_recent_itineraries(self, user_id: str, limit: int = 3) -> list[dict]:
        with SessionLocal() as db:
            rows = db.query(ItineraryModel)\
                .filter_by(user_id=user_id)\
                .order_by(ItineraryModel.id.desc())\
                .limit(limit)\
                .all()
            result = []
            for row in rows:
                trip = json.loads(row.data)
                trip["saved_at"] = row.saved_at.isoformat()
                result.append(trip)
            return result

    def save_itinerary(self, user_id: str, itinerary: dict):
        with SessionLocal() as db:
            db.add(ItineraryModel(
                user_id=user_id,
                data=json.dumps(itinerary, ensure_ascii=False),
                saved_at=datetime.now(),
            ))
            db.commit()
        logger.info("行程已保存: %s → %s", user_id, itinerary.get("destination", ""))

    # ===== 愿望清单 =====

    def get_wishlist(self, user_id: str) -> list[dict]:
        with SessionLocal() as db:
            rows = db.query(Wishlist)\
                .filter_by(user_id=user_id)\
                .order_by(Wishlist.sort_order, Wishlist.id)\
                .all()
            return [{
                "id": r.id, "name": r.name, "category": r.category,
                "city": r.city, "note": r.note, "checked": bool(r.checked),
                "sort_order": r.sort_order, "created_at": r.created_at.isoformat(),
            } for r in rows]

    def add_wish(self, user_id: str, name: str, category: str = "", note: str = "", city: str = "") -> int:
        with SessionLocal() as db:
            max_order = db.query(Wishlist)\
                .filter_by(user_id=user_id)\
                .order_by(Wishlist.sort_order.desc())\
                .first()
            sort_order = (max_order.sort_order + 1) if max_order else 1
            row = Wishlist(
                user_id=user_id, name=name, category=category, city=city, note=note,
                checked=0, sort_order=sort_order,
            )
            db.add(row)
            db.commit()
            return row.id

    def update_wish(self, user_id: str, wish_id: int, **fields):
        allowed = {"name", "category", "city", "note", "checked", "sort_order"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        with SessionLocal() as db:
            row = db.query(Wishlist).filter_by(user_id=user_id, id=wish_id).first()
            if row:
                for k, v in updates.items():
                    setattr(row, k, 1 if k == "checked" and v else v)
                db.commit()

    def delete_wish(self, user_id: str, wish_id: int):
        with SessionLocal() as db:
            row = db.query(Wishlist).filter_by(user_id=user_id, id=wish_id).first()
            if row:
                db.delete(row)
                db.commit()

    # ===== 清空（测试用） =====

    def clear_all(self):
        with SessionLocal() as db:
            db.query(Profile).delete()
            db.query(ItineraryModel).delete()
            db.query(Wishlist).delete()
            db.commit()
        logger.info("全部记忆已清空")


_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
        # 建表
        from app.db import init_db
        init_db()
        logger.info("SQLite 记忆存储已初始化 (ORM)")
    return _store
