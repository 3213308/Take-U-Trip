# app/tools/transport.py
"""交通搜索工具"""

import logging
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.adapters.factory import get_transport_adapter

logger = logging.getLogger(__name__)


class SearchTransportInput(BaseModel):
    departure: str = Field(description="出发城市")
    destination: str = Field(description="目的城市")
    date: str = Field(description="出发日期，YYYY-MM-DD")
    transport_type: str = Field(default="all", description="交通方式：all/高铁/飞机")


@tool(args_schema=SearchTransportInput)
async def search_transport(departure: str, destination: str, date: str,
                           transport_type: str = "all") -> str:
    """搜索城际交通（高铁/飞机），返回班次、出发到达时间、时长、价格。

    当用户需要跨城市出行、查机票火车票时使用。
    """
    logger.info("search_transport: %s→%s, %s", departure, destination, date)
    try:
        adapter = get_transport_adapter()
        results = await adapter.search(departure, destination, date, transport_type)
        if not results:
            return f"未找到{departure}到{destination}在{date}的交通信息"

        lines = [f"{departure}→{destination}（{date}）交通选项："]
        for i, r in enumerate(results, 1):
            price_str = f"{r['price']}元" if r.get("price") else "价格请以12306为准"
            lines.append(
                f"{i}. [{r['type']}] {r['number']} {r['departure']}-{r['arrival']} "
                f"时长{r['duration']} {price_str}（{r['seat']}）"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception("search_transport 异常")
        return f"交通查询失败：{e}"
