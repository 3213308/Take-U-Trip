# app/adapters/mock/attraction.py
"""Mock 景点数据"""

from app.adapters.base import BaseAttractionAdapter

_MOCK_ATTRACTIONS: dict[str, list[dict]] = {
    "成都": [
        {"name": "大熊猫繁育研究基地", "category": "自然景观", "ticket": 55,
         "open_time": "07:30-18:00", "rating": 4.9, "duration": "3小时", "location": "成华区"},
        {"name": "宽窄巷子", "category": "历史古迹", "ticket": 0,
         "open_time": "全天", "rating": 4.6, "duration": "2小时", "location": "青羊区"},
        {"name": "锦里古街", "category": "历史古迹", "ticket": 0,
         "open_time": "全天", "rating": 4.5, "duration": "2小时", "location": "武侯区"},
        {"name": "武侯祠", "category": "历史古迹", "ticket": 50,
         "open_time": "08:00-20:00", "rating": 4.7, "duration": "2小时", "location": "武侯区"},
        {"name": "杜甫草堂", "category": "历史古迹", "ticket": 50,
         "open_time": "08:00-18:30", "rating": 4.6, "duration": "1.5小时", "location": "青羊区"},
        {"name": "春熙路", "category": "购物", "ticket": 0,
         "open_time": "全天", "rating": 4.4, "duration": "2小时", "location": "锦江区"},
    ],
    "北京": [
        {"name": "故宫博物院", "category": "历史古迹", "ticket": 60,
         "open_time": "08:30-17:00", "rating": 4.9, "duration": "4小时", "location": "东城区"},
        {"name": "长城(八达岭)", "category": "历史古迹", "ticket": 40,
         "open_time": "07:30-17:30", "rating": 4.8, "duration": "4小时", "location": "延庆区"},
    ],
}

_DEFAULT = [
    {"name": "城市中心公园", "category": "自然景观", "ticket": 0,
     "open_time": "全天", "rating": 4.3, "duration": "2小时", "location": "市中心"},
]


class MockAttractionAdapter(BaseAttractionAdapter):
    async def search(self, city: str, category: str = "", limit: int = 10) -> list[dict]:
        results = _MOCK_ATTRACTIONS.get(city, _DEFAULT)
        if category:
            results = [a for a in results if a["category"] == category]
        return results[:limit]
