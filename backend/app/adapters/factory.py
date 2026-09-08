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
    if _settings.ADAPTER_MODE == "mock":
        return MockTransportAdapter()
    # Real 适配器后续实现
    raise NotImplementedError("Real transport adapter 尚未实现")


def get_hotel_adapter() -> BaseHotelAdapter:
    if _settings.ADAPTER_MODE == "mock":
        return MockHotelAdapter()
    raise NotImplementedError("Real hotel adapter 尚未实现")


def get_attraction_adapter() -> BaseAttractionAdapter:
    if _settings.ADAPTER_MODE == "mock":
        return MockAttractionAdapter()
    raise NotImplementedError("Real attraction adapter 尚未实现")


def get_weather_adapter() -> BaseWeatherAdapter:
    if _settings.ADAPTER_MODE == "mock":
        return MockWeatherAdapter()
    raise NotImplementedError("Real weather adapter 尚未实现")


def get_restaurant_adapter() -> BaseRestaurantAdapter:
    if _settings.ADAPTER_MODE == "mock":
        return MockRestaurantAdapter()
    raise NotImplementedError("Real restaurant adapter 尚未实现")
