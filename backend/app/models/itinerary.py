# app/models/itinerary.py
"""结构化行程数据模型 — Pydantic v2

生产级要点：
1. 每个字段都有 description，模型靠它理解字段含义
2. 非关键字段给 default，避免模型漏一个字段就整体解析失败
3. 嵌套模型（Itinerary → DayPlan → Activity）对应真实行程结构
"""

from pydantic import BaseModel, Field


class Activity(BaseModel):
    """单个活动"""
    time: str = Field(description="活动时间段，格式 HH:MM-HH:MM，如 09:00-11:30")
    name: str = Field(description="活动名称，如'参观故宫博物院'")
    location: str = Field(description="活动地点")
    category: str = Field(description="活动分类：交通/景点/餐饮/住宿/自由活动")
    cost: float = Field(default=0.0, description="该活动费用（元），免费为0")
    notes: str = Field(default="", description="备注，如'需提前预约'、'建议穿舒适鞋子'")
    lng: float | None = Field(default=None, description="活动地点经度，工具返回了就填，没有留空")
    lat: float | None = Field(default=None, description="活动地点纬度，工具返回了就填，没有留空")


class DayPlan(BaseModel):
    """单日行程"""
    date: str = Field(description="日期，YYYY-MM-DD 格式")
    theme: str = Field(default="", description="当日主题，如'市区经典游'、'近郊自然游'")
    activities: list[Activity] = Field(description="当日活动列表，按时间排序")
    daily_budget: float = Field(default=0.0, description="当日总花费（元）")


class Itinerary(BaseModel):
    """完整行程"""
    destination: str = Field(description="目的地城市")
    days: int = Field(description="行程总天数")
    total_budget: float = Field(default=0.0, description="总预算（元）")
    transport_cost: float = Field(default=0.0, description="交通费用（元）")
    transport_suggestions: list[str] = Field(
        default_factory=list,
        description="交通方式对比建议，当用户询问怎么去时，必须列出高铁和飞机的时间价格对比"
    )
    accommodation_cost: float = Field(default=0.0, description="住宿费用（元）")
    food_cost: float = Field(default=0.0, description="餐饮费用（元）")
    attraction_cost: float = Field(default=0.0, description="景点门票费用（元）")
    days_plan: list[DayPlan] = Field(description="每日行程列表")
    warnings: list[str] = Field(default_factory=list, description="警告信息")
