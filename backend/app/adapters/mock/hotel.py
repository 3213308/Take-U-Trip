# app/adapters/mock/hotel.py
"""Mock 酒店数据"""

from app.adapters.base import BaseHotelAdapter

_MOCK_HOTELS: dict[str, list[dict]] = {
    "成都": [
        {"name": "成都太古里亚朵酒店", "stars": "四星", "price": 458, "rating": 4.8,
         "location": "锦江区太古里", "facilities": ["免费WiFi", "早餐", "健身房"]},
        {"name": "成都春熙路全季酒店", "stars": "三星", "price": 328, "rating": 4.6,
         "location": "锦江区春熙路", "facilities": ["免费WiFi", "早餐"]},
        {"name": "成都瑞吉酒店", "stars": "五星", "price": 1280, "rating": 4.9,
         "location": "锦江区", "facilities": ["免费WiFi", "早餐", "泳池", "健身房", "SPA"]},
        {"name": "成都宽窄巷子如家", "stars": "二星", "price": 198, "rating": 4.2,
         "location": "青羊区宽窄巷子", "facilities": ["免费WiFi"]},
    ],
}

_DEFAULT = [
    {"name": "城市中心商务酒店", "stars": "四星", "price": 400, "rating": 4.5,
     "location": "市中心", "facilities": ["免费WiFi", "早餐"]},
]


class MockHotelAdapter(BaseHotelAdapter):
    async def search(self, city: str, check_in: str, check_out: str,
                     budget_range: list[float] | None = None, stars: str = "") -> list[dict]:
        results = _MOCK_HOTELS.get(city, _DEFAULT)
        if stars:
            results = [h for h in results if h["stars"] == stars]
        if budget_range and len(budget_range) == 2:
            results = [h for h in results if budget_range[0] <= h["price"] <= budget_range[1]]
        return results
