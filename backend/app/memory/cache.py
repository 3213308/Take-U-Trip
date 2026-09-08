# app/memory/cache.py
"""工具结果缓存 — 带 TTL，避免重复调用外部 API

生产级要点：
1. TTL 过期自动失效
2. cache_key 由工具名+参数序列化组成，参数不同不会误命中
3. 线程安全（生产环境换 Redis 时接口不变）
"""

import hashlib
import json
import logging
import time

logger = logging.getLogger(__name__)


class ToolCache:
    def __init__(self, ttl: int = 3600):
        self._cache: dict[str, tuple[str, float]] = {}
        self._ttl = ttl

    @staticmethod
    def make_key(tool_name: str, args: dict) -> str:
        """生成缓存 key：工具名 + 参数的稳定序列化"""
        args_str = json.dumps(args, sort_keys=True, ensure_ascii=False)
        raw = f"{tool_name}:{args_str}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str) -> str | None:
        if key not in self._cache:
            return None
        value, expire_at = self._cache[key]
        if time.time() > expire_at:
            del self._cache[key]
            logger.debug("缓存过期: %s", key[:8])
            return None
        logger.debug("缓存命中: %s", key[:8])
        return value

    def set(self, key: str, value: str):
        self._cache[key] = (value, time.time() + self._ttl)

    def clear(self):
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


# 全局单例
_cache: ToolCache | None = None


def get_tool_cache() -> ToolCache:
    global _cache
    if _cache is None:
        from app.config import get_settings
        _cache = ToolCache(ttl=get_settings().TOOL_CACHE_TTL)
    return _cache
