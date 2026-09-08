# mcp_server/travel_server.py
"""Take-U-Trip MCP Server

通过 MCP 协议对外暴露旅游查询能力，以 stdio 方式通信。
MCP Server 是独立进程：客户端启动它 → 握手 → 发现工具 → 调用工具。

关键约束：stdio 通道传输协议数据，禁止 print（会污染通道），
日志只能走 stderr（logging 默认就是 stderr）。
"""

import logging

from mcp.server.fastmcp import FastMCP

from app.adapters.factory import get_attraction_adapter, get_weather_adapter

logging.basicConfig(level=logging.WARNING)

mcp = FastMCP("take-u-trip")


@mcp.tool()
async def mcp_get_weather(city: str, date: str = "") -> str:
    """查询指定城市的天气，返回天气状况、温度、风力和降水概率。

    Args:
        city: 城市名称，如"成都"
        date: 日期 YYYY-MM-DD，可选
    """
    adapter = get_weather_adapter()
    target = date or "2025-10-01"
    results = await adapter.get_weather(city, (target, target))
    if not results:
        return f"未找到{city}的天气"
    w = results[0]
    return (
        f"{city} {w['date']}：{w['weather']}，"
        f"{w['temp_low']}~{w['temp_high']}℃，{w['wind']}，"
        f"降水概率{w['rain_probability']}%"
    )


@mcp.tool()
async def mcp_search_attractions(city: str, category: str = "", limit: int = 5) -> str:
    """搜索城市热门景点，返回名称、分类、门票、开放时间、评分。

    Args:
        city: 城市名称
        category: 分类筛选：自然景观/历史古迹/购物，留空返回全部
        limit: 返回数量上限
    """
    adapter = get_attraction_adapter()
    results = await adapter.search(city, category, limit)
    if not results:
        return f"未找到{city}的景点"

    lines = [f"{city}景点（来自MCP Server）："]
    for i, a in enumerate(results, 1):
        ticket = "免费" if a["ticket"] == 0 else f"{a['ticket']}元"
        lines.append(
            f"{i}. {a['name']}｜{a['category']}｜门票{ticket}｜"
            f"{a['open_time']}｜评分{a['rating']}｜游玩{a['duration']}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    # stdio 传输：server 的输入输出就是协议通道
    mcp.run(transport="stdio")
