# app/tools/weather.py
"""天气查询工具 — 通过 Adapter 获取数据"""

import logging
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.adapters.factory import get_weather_adapter

logger = logging.getLogger(__name__)


class GetWeatherInput(BaseModel):
    city: str = Field(description="城市名称，如'北京'、'成都'")
    start_date: str = Field(description="开始日期，YYYY-MM-DD")
    end_date: str = Field(default="", description="结束日期，YYYY-MM-DD，为空则只查开始日期")


@tool(args_schema=GetWeatherInput)
async def get_weather(city: str, start_date: str, end_date: str = "") -> str:
    """查询城市天气预报，返回天气状况、温度范围、风力和降水概率。

    当用户询问天气、穿衣建议、是否带伞时使用。
    """
    logger.info("get_weather: city=%s, %s~%s", city, start_date, end_date)
    try:
        adapter = get_weather_adapter()
        results = await adapter.get_weather(city, (start_date, end_date or start_date))
        if not results:
            return f"未找到{city}的天气数据"

        lines = [f"{city}天气预报："]
        for w in results:
            rain = f" 降水概率{w['rain_probability']}%" if w.get("rain_probability", 0) > 30 else ""
            lines.append(
                f"- {w['date']}：{w['weather']} {w['temp_low']}~{w['temp_high']}℃ {w['wind']}{rain}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception("get_weather 异常")
        return f"天气查询失败：{e}"
