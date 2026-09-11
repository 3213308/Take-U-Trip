# app/tools/restaurant.py
"""餐厅搜索工具"""

import logging
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.adapters.factory import get_restaurant_adapter

logger = logging.getLogger(__name__)


class SearchRestaurantsInput(BaseModel):
    city: str = Field(description="城市")
    cuisine: str = Field(default="", description="菜系：川菜/粤菜/火锅/小吃等")
    budget: float = Field(default=0, description="人均预算上限（元），0表示不限")
    meal_type: str = Field(default="", description="餐次：早餐/午餐/晚餐")


@tool(args_schema=SearchRestaurantsInput)
async def search_restaurants(city: str, cuisine: str = "",
                             budget: float = 0, meal_type: str = "") -> str:
    """搜索餐厅，返回名称、菜系、人均价格、评分、招牌菜。

    当用户询问吃什么、餐厅推荐时使用。
    """
    logger.info("search_restaurants: city=%s, cuisine=%s", city, cuisine)
    try:
        adapter = get_restaurant_adapter()
        results = await adapter.search(city, cuisine, budget, meal_type)
        if not results:
            return f"未找到{city}符合条件的餐厅"

        lines = [f"{city}餐厅推荐："]
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. {r['name']}（{r['cuisine']}）人均{r['avg_price']}元 "
                f"评分{r['rating']} 招牌：{r['signature']} "
                f"坐标：{r.get('lnglat', '无')}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception("search_restaurants 异常")
        return f"餐厅搜索失败：{e}"
