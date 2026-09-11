# app/adapters/real/route.py
"""高德路径规划 Real Adapter"""

import logging
import httpx

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
DRIVING_URL = "https://restapi.amap.com/v3/direction/driving"

# 进程级地理编码缓存：同一次规划里同一地名会被多段路线反复编码，
# 缓存后同一 (城市,地名) 只请求一次，省高德配额也更快。None 结果也缓存，避免反复失败重试。
_GEOCODE_CACHE: dict[tuple[str, str], str | None] = {}


class AmapRouteAdapter:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def _geocode(self, city: str, location: str) -> str | None:
        """地名 → 经纬度 'lng,lat'（带进程缓存）"""
        cache_key = (city, location)
        if cache_key in _GEOCODE_CACHE:
            return _GEOCODE_CACHE[cache_key]
        async with httpx.AsyncClient() as client:
            r = await client.get(GEOCODE_URL, params={
                "key": self.api_key,
                "address": location,
                "city": city,
            })
            data = r.json()
        geocodes = data.get("geocodes", [])
        result = geocodes[0].get("location") if geocodes else None
        _GEOCODE_CACHE[cache_key] = result
        return result

    async def calculate(self, city: str, from_loc: str, to_loc: str) -> dict:
        origin = await self._geocode(city, from_loc)
        destination = await self._geocode(city, to_loc)
        if not origin or not destination:
            return {"minutes": 30, "distance_km": 10, "note": "坐标解析失败，使用估算值"}

        async with httpx.AsyncClient() as client:
            r = await client.get(DRIVING_URL, params={
                "key": self.api_key,
                "origin": origin,
                "destination": destination,
            })
            data = r.json()

        if data.get("status") != "1":
            return {"minutes": 30, "distance_km": 10, "note": "路线规划失败，使用估算值"}

        paths = data.get("route", {}).get("paths", [])
        if not paths:
            return {"minutes": 30, "distance_km": 10, "note": "无路线数据"}

        p = paths[0]
        return {
            "minutes": round(int(p["duration"]) / 60),
            "distance_km": round(int(p["distance"]) / 1000, 1),
            "note": "",
        }
