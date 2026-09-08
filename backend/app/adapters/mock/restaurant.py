# app/adapters/mock/restaurant.py
"""Mock 餐厅数据"""

from app.adapters.base import BaseRestaurantAdapter

_MOCK_RESTAURANTS: dict[str, list[dict]] = {
    "成都": [
        {"name": "蜀大侠火锅", "cuisine": "川菜/火锅", "avg_price": 120, "rating": 4.8,
         "signature": "大刀腰片、极品鹅肠", "meal_type": "晚餐"},
        {"name": "陈麻婆豆腐", "cuisine": "川菜", "avg_price": 60, "rating": 4.6,
         "signature": "麻婆豆腐、夫妻肺片", "meal_type": "午餐/晚餐"},
        {"name": "龙抄手(春熙路店)", "cuisine": "小吃", "avg_price": 35, "rating": 4.4,
         "signature": "龙抄手、钟水饺", "meal_type": "早餐/午餐"},
        {"name": "饕林餐厅", "cuisine": "川菜", "avg_price": 80, "rating": 4.7,
         "signature": "钵钵鸡、甜烧白", "meal_type": "午餐/晚餐"},
    ],
}

_DEFAULT = [
    {"name": "本地特色餐厅", "cuisine": "地方菜", "avg_price": 70, "rating": 4.3,
     "signature": "招牌菜", "meal_type": "午餐/晚餐"},
]


class MockRestaurantAdapter(BaseRestaurantAdapter):
    async def search(self, city: str, cuisine: str = "",
                     budget: float = 0, meal_type: str = "") -> list[dict]:
        results = _MOCK_RESTAURANTS.get(city, _DEFAULT)
        if cuisine:
            results = [r for r in results if cuisine in r["cuisine"]]
        if budget > 0:
            results = [r for r in results if r["avg_price"] <= budget]
        if meal_type:
            results = [r for r in results if meal_type in r["meal_type"]]
        return results
