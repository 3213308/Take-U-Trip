# app/adapters/base.py
"""Adapter 抽象基类 — 定义所有外部数据源的统一接口

Adapter 模式的核心思想：
- 工具层只依赖抽象接口，不关心数据来自 Mock 还是真实 API
- Mock Adapter 用于开发测试，Real Adapter 用于生产
- 切换数据源只需要改配置 ADAPTER_MODE，不改工具代码
"""

from abc import ABC, abstractmethod


class BaseTransportAdapter(ABC):
    @abstractmethod
    async def search(self, departure: str, destination: str, date: str,
                     transport_type: str = "all") -> list[dict]:
        """搜索交通方式"""
        ...


class BaseHotelAdapter(ABC):
    @abstractmethod
    async def search(self, city: str, check_in: str, check_out: str,
                     budget_range: list[float] | None = None,
                     stars: str = "") -> list[dict]:
        """搜索酒店"""
        ...


class BaseAttractionAdapter(ABC):
    @abstractmethod
    async def search(self, city: str, category: str = "", limit: int = 10) -> list[dict]:
        """搜索景点"""
        ...


class BaseWeatherAdapter(ABC):
    @abstractmethod
    async def get_weather(self, city: str, date_range: tuple[str, str]) -> list[dict]:
        """查询天气"""
        ...


class BaseRestaurantAdapter(ABC):
    @abstractmethod
    async def search(self, city: str, cuisine: str = "",
                     budget: float = 0, meal_type: str = "") -> list[dict]:
        """搜索餐厅"""
        ...
