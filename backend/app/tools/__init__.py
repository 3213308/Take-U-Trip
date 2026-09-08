# app/tools/__init__.py
"""工具注册中心 — 统一管理全部 7 个工具"""

from langchain_core.tools import BaseTool

from app.tools.attraction import search_attractions
from app.tools.budget import calculate_budget
from app.tools.hotel import search_hotels
from app.tools.restaurant import search_restaurants
from app.tools.route import calculate_route
from app.tools.transport import search_transport
from app.tools.weather import get_weather


def get_all_tools() -> list[BaseTool]:
    """返回所有可用工具"""
    return [
        search_transport,
        search_hotels,
        search_attractions,
        get_weather,
        search_restaurants,
        calculate_route,
        calculate_budget,
    ]


def get_tool_map() -> dict[str, BaseTool]:
    """工具名→工具对象映射"""
    return {t.name: t for t in get_all_tools()}
