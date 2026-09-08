# app/tools/budget.py
"""预算汇总工具 — 纯计算"""

import logging
from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BudgetItem(BaseModel):
    category: str = Field(description="费用类别：交通/住宿/餐饮/门票/其他")
    amount: float = Field(description="金额（元）")
    description: str = Field(default="", description="费用说明")


class CalculateBudgetInput(BaseModel):
    items: list[BudgetItem] = Field(description="费用明细列表")
    total_budget: float = Field(default=0, description="用户总预算，用于对比是否超支")


@tool(args_schema=CalculateBudgetInput)
async def calculate_budget(items: list[dict], total_budget: float = 0) -> str:
    """汇总各项费用，计算总额并与用户预算对比，超支时给出警告和建议。

    在规划完行程后使用，确保费用在预算范围内。
    """
    category_totals: dict[str, float] = {}
    grand_total = 0.0

    for item in items:
        cat = item.category
        amt = float(item.amount)
        category_totals[cat] = category_totals.get(cat, 0) + amt
        grand_total += amt

    lines = ["预算汇总："]
    for cat, amt in category_totals.items():
        pct = (amt / grand_total * 100) if grand_total > 0 else 0
        lines.append(f"- {cat}：{amt:.0f}元（{pct:.0f}%）")
    lines.append(f"\n合计：{grand_total:.0f}元")

    if total_budget > 0:
        diff = grand_total - total_budget
        if diff > 0:
            lines.append(f"超预算{diff:.0f}元（预算{total_budget:.0f}元），建议降低住宿标准或减少景点")
        else:
            lines.append(f"在预算内，剩余{-diff:.0f}元")

    logger.info("calculate_budget: total=%.0f, budget=%.0f", grand_total, total_budget)
    return "\n".join(lines)
