# app/memory/store.py
"""长期记忆存储 — 用户画像 + 历史行程

MVP 阶段用内存存储，生产环境替换为数据库（接口不变）
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryStore:
    def __init__(self):
        self._profiles: dict[str, dict] = {}
        self._itineraries: dict[str, list[dict]] = {}

    # ===== 用户画像 =====

    def get_profile(self, user_id: str) -> dict:
        return self._profiles.get(user_id, {})

    def save_profile(self, user_id: str, profile: dict):
        profile["updated_at"] = datetime.now().isoformat()
        self._profiles[user_id] = profile
        logger.info("用户画像已更新: %s", user_id)

    def merge_profile(self, user_id: str, new_preferences: dict):
        """合并新提取的偏好到已有画像（不覆盖，只追加/更新）"""
        existing = self._profiles.get(user_id, {})
        for key, value in new_preferences.items():
            if isinstance(value, list) and key in existing:
                # 列表类型：合并去重
                merged = list(set(existing[key] + value))
                existing[key] = merged
            elif value:
                existing[key] = value
        existing["updated_at"] = datetime.now().isoformat()
        self._profiles[user_id] = existing

    # ===== 历史行程 =====

    def get_recent_itineraries(self, user_id: str, limit: int = 3) -> list[dict]:
        trips = self._itineraries.get(user_id, [])
        return trips[-limit:]

    def save_itinerary(self, user_id: str, itinerary: dict):
        if user_id not in self._itineraries:
            self._itineraries[user_id] = []
        self._itineraries[user_id].append({
            "itinerary": itinerary,
            "saved_at": datetime.now().isoformat(),
        })
        logger.info("行程已保存: %s → %s", user_id, itinerary.get("destination", ""))

    def clear_all(self):
        """清空全部记忆（评估/测试用）"""
        self._profiles.clear()
        self._itineraries.clear()


_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store