# app/adapters/mock/weather.py
"""Mock 天气数据"""

from app.adapters.base import BaseWeatherAdapter

_MOCK_WEATHER: dict[str, list[dict]] = {
    "成都": [
        {"date": "2025-10-01", "weather": "小雨", "temp_high": 19, "temp_low": 14,
         "wind": "微风", "rain_probability": 80},
        {"date": "2025-10-02", "weather": "阴", "temp_high": 22, "temp_low": 15,
         "wind": "微风", "rain_probability": 30},
    ],
    "北京": [
        {"date": "2025-10-01", "weather": "晴", "temp_high": 22, "temp_low": 10,
         "wind": "北风3级", "rain_probability": 0},
    ],
}

_DEFAULT = [
    {"date": "2025-10-01", "weather": "晴", "temp_high": 25, "temp_low": 15,
     "wind": "微风", "rain_probability": 10},
]


class MockWeatherAdapter(BaseWeatherAdapter):
    async def get_weather(self, city: str, date_range: tuple[str, str]) -> list[dict]:
        return _MOCK_WEATHER.get(city, _DEFAULT)
