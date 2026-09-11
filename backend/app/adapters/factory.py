# app/adapters/factory.py
"""Adapter 工厂 — 根据配置返回 Mock 或 Real 适配器

生产级做法：工具层不直接 new Adapter，而是通过工厂获取，
切换数据源只需要改 .env 里的 ADAPTER_MODE
"""

from app.config import get_settings
from app.adapters.base import (
    BaseAttractionAdapter,
    BaseHotelAdapter,
    BaseRestaurantAdapter,
    BaseTransportAdapter,
    BaseWeatherAdapter,
)
from app.adapters.mock.attraction import MockAttractionAdapter
from app.adapters.mock.hotel import MockHotelAdapter
from app.adapters.mock.restaurant import MockRestaurantAdapter
from app.adapters.mock.transport import MockTransportAdapter
from app.adapters.mock.weather import MockWeatherAdapter

_settings = get_settings()


def get_transport_adapter() -> BaseTransportAdapter:
    if _settings.ADAPTER_MODE == "real":
        from app.adapters.real.train12306 import Train12306Adapter
        return Train12306Adapter()
    return MockTransportAdapter()


def get_hotel_adapter() -> BaseHotelAdapter:
    if _settings.ADAPTER_MODE == "real":
        from app.adapters.real.poi import AmapHotelAdapter
        return AmapHotelAdapter(_settings.AMAP_API_KEY)
    return MockHotelAdapter()


def get_attraction_adapter() -> BaseAttractionAdapter:
    if _settings.ADAPTER_MODE == "real":
        from app.adapters.real.poi import AmapAttractionAdapter
        return AmapAttractionAdapter(_settings.AMAP_API_KEY)
    return MockAttractionAdapter()


def get_weather_adapter() -> BaseWeatherAdapter:
    if _settings.ADAPTER_MODE == "real":
        from app.adapters.real.weather import QWeatherAdapter
        return QWeatherAdapter(_settings.QWEATHER_API_KEY, _settings.QWEATHER_API_HOST)
    return MockWeatherAdapter()



def get_restaurant_adapter() -> BaseRestaurantAdapter:
    if _settings.ADAPTER_MODE == "real":
        from app.adapters.real.poi import AmapRestaurantAdapter
        return AmapRestaurantAdapter(_settings.AMAP_API_KEY)
    return MockRestaurantAdapter()