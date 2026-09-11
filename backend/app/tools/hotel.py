# app/tools/hotel.py
"""酒店搜索工具"""

import logging
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.adapters.factory import get_hotel_adapter

logger = logging.getLogger(__name__)


class SearchHotelsInput(BaseModel):
    city: str = Field(description="城市")
    check_in: str = Field(description="入住日期，YYYY-MM-DD")
    check_out: str = Field(description="退房日期，YYYY-MM-DD")
    budget_min: float = Field(default=0, description="最低价格（元/晚）")
    budget_max: float = Field(default=99999, description="最高价格（元/晚）")
    stars: str = Field(default="", description="星级：二星/三星/四星/五星")


@tool(args_schema=SearchHotelsInput)
async def search_hotels(city: str, check_in: str, check_out: str,
                        budget_min: float = 0, budget_max: float = 99999,
                        stars: str = "") -> str:
    """搜索酒店，返回名称、星级、每晚价格、评分、位置、设施。

    当用户需要住宿推荐时使用。
    """
    logger.info("search_hotels: city=%s, %s~%s", city, check_in, check_out)
    try:
        adapter = get_hotel_adapter()
        results = await adapter.search(city, check_in, check_out,
                                       [budget_min, budget_max], stars)
        if not results:
            return f"未找到{city}符合条件的酒店"

        lines = [f"{city}酒店推荐（{check_in}至{check_out}）："]
        for i, h in enumerate(results, 1):
            facilities = "、".join(h["facilities"])
            lines.append(
                f"{i}. {h['name']}（{h['stars']}）{h['price']}元/晚 "
                f"评分{h['rating']} 位置：{h['location']} 设施：{facilities} "
                f"坐标：{h.get('lnglat', '无')}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception("search_hotels 异常")
        return f"酒店搜索失败：{e}"
