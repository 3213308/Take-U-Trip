# app/adapters/real/poi.py
"""高德 POI 搜索 Real Adapter — 景点/餐厅/酒店共用"""

import asyncio
import logging
import httpx
from app.adapters.base import BaseAttractionAdapter, BaseRestaurantAdapter, BaseHotelAdapter

logger = logging.getLogger(__name__)

POI_URL = "https://restapi.amap.com/v3/place/text"

# 泛词"景点/景区"在高德默认权重下会被带偏到商务/住宅密集区的冷门 POI，
# 改用更具体的旅游名词扇出召回，才能稳定得到真正的景区/博物馆/古镇。
_ATTRACTION_PANEL = {
    "": ["古镇", "博物馆", "遗址", "公园", "寺", "步行街", "动物园", "景区"],
    "历史古迹": ["博物馆", "遗址", "古镇", "寺", "名人故居", "纪念馆"],
    "自然景观": ["森林公园", "湿地公园", "山", "湖", "动物园", "自然保护区", "景区"],
    "购物": ["购物中心", "商业街"],
}
# 噪声类目/命名：这些不是给游客的"景点"，泛词召回时剔除
_NOISE_CATEGORY = ("写字楼", "商务住宅", "住宅", "购物相关", "家电", "数码", "餐厅", "快餐")
_NOISE_NAME = ("打卡点", "装置", "雕塑", "展品", "售楼", "公寓", "大厦")


class AmapPOIBase:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def _search(self, city: str, keywords: str, limit: int = 10) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(POI_URL, params={
                "key": self.api_key,
                "keywords": keywords,
                "city": city,
                "citylimit": "true",
                "offset": limit,
                "page": 1,
                "extensions": "all",
            })
            data = r.json()

        if data.get("status") != "1":
            logger.warning("高德 POI 错误: %s", data.get("info"))
            return []

        result = []
        for p in data.get("pois", []):
            _raw_rating = p.get("biz_ext", {}).get("rating", "")
            _rating = float(_raw_rating) if _raw_rating and float(_raw_rating) > 0 else 4.0

            result.append({
                "name": p.get("name", ""),
                "category": p.get("type", "").split(";")[-1] if p.get("type") else "",
                "cuisine": p.get("type", "").split(";")[-1] if p.get("type") else "",
                "ticket": 0,
                "open_time": "全天",
                "rating": _rating,
                "duration": "2小时",
                "avg_price": 80,
                "signature": "特色菜",
                "location": p.get("address", "") or p.get("pname", ""),
                "lnglat": p.get("location", ""),
                "facilities": ["WiFi", "热水"],
                "stars": "经济型",
                "price": 200,
            })

        return result


class AmapAttractionAdapter(AmapPOIBase, BaseAttractionAdapter):
    async def search(self, city: str, category: str = "", limit: int = 10) -> list[dict]:
        keywords_list = _ATTRACTION_PANEL.get(category, _ATTRACTION_PANEL[""])
        merged: list[dict] = []
        seen: set[str] = set()
        # 顺序扇出，避免触发高德 3 QPS 限流
        for kw in keywords_list:
            for item in await self._search(city, kw, 8):
                cat, name = item.get("category", ""), item.get("name", "")
                if any(n in cat for n in _NOISE_CATEGORY) or any(n in name for n in _NOISE_NAME):
                    continue
                if name in seen:
                    continue
                seen.add(name)
                merged.append(item)
            await asyncio.sleep(0.35)  # 高德免费档 3 QPS，顺序扇出需拉开间隔避免 CUQPS 限流
        # 评分高的优先，保证返回的是真正值得去的景点
        merged.sort(key=lambda x: x.get("rating", 0), reverse=True)
        return merged[:limit]


class AmapRestaurantAdapter(AmapPOIBase, BaseRestaurantAdapter):
    async def search(self, city: str, cuisine: str = "", budget: float = 0, meal_type: str = "") -> list[dict]:
        keywords = cuisine or "餐厅"
        return await self._search(city, keywords, 10)


class AmapHotelAdapter(AmapPOIBase, BaseHotelAdapter):
    async def search(self, city: str, check_in: str = "", check_out: str = "",
                     budget_range: list[float] | None = None, stars: str = "") -> list[dict]:
        return await self._search(city, "酒店", 10)
