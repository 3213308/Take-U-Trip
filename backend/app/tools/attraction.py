# app/tools/attraction.py
"""景点搜索工具 — 通过 Adapter 获取数据"""

import logging
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.adapters.factory import get_attraction_adapter

logger = logging.getLogger(__name__)


class SearchAttractionsInput(BaseModel):
    city: str = Field(description="城市名称")
    category: str = Field(default="", description="分类：自然景观/历史古迹/购物/美食")
    limit: int = Field(default=10, description="返回数量上限")


@tool(args_schema=SearchAttractionsInput)
async def search_attractions(city: str, category: str = "", limit: int = 10) -> str:
    """搜索城市热门景点，返回名称、分类、门票、开放时间、评分、建议游玩时长。

    当用户询问去哪玩、景点推荐时使用。
    """
    logger.info("search_attractions: city=%s, category=%s", city, category)
    try:
        adapter = get_attraction_adapter()
        results = await adapter.search(city, category, limit)
        if not results:
            return f"未找到{city}的景点信息"

        lines = [f"{city}景点推荐："]
        for i, a in enumerate(results, 1):
            ticket = "免费" if a["ticket"] == 0 else f"{a['ticket']}元"
            lines.append(
                f"{i}. {a['name']}（{a['category']}）门票：{ticket} "
                f"开放：{a['open_time']} 评分：{a['rating']} 建议游玩：{a['duration']} "
                f"坐标：{a.get('lnglat', '无')}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception("search_attractions 异常")
        return f"景点搜索失败：{e}"
