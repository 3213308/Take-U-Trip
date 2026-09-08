# app/tools/route.py
"""路线时间计算工具 — 纯计算，不依赖外部 API"""

import logging
from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 城际交通时间（简化数据）
_INTERCITY = {
    ("北京", "成都"): {"distance": 1800, "flight": "2h55m", "train": "7h35m"},
    ("上海", "成都"): {"distance": 1950, "flight": "3h15m", "train": "12h14m"},
    ("北京", "上海"): {"distance": 1300, "flight": "2h15m", "train": "4h29m"},
}

# 市内景点间交通时间（分钟）
_INTRACITY = {
    ("宽窄巷子", "锦里古街"): 25,
    ("锦里古街", "武侯祠"): 5,
    ("武侯祠", "春熙路"): 20,
    ("春熙路", "大熊猫繁育研究基地"): 40,
    ("宽窄巷子", "杜甫草堂"): 15,
    ("锦里古街", "春熙路"): 20,
}


class CalculateRouteInput(BaseModel):
    from_location: str = Field(description="起点")
    to_location: str = Field(description="终点")
    transport_mode: str = Field(default="auto", description="交通方式：auto/飞机/高铁/公共交通")


@tool(args_schema=CalculateRouteInput)
async def calculate_route(from_location: str, to_location: str,
                          transport_mode: str = "auto") -> str:
    """计算两点间的交通时间和距离，用于安排行程时间衔接。

    支持城际交通和市内景点间交通。
    """
    # 查城际
    for (a, b), info in _INTERCITY.items():
        if {from_location, to_location} == {a, b}:
            if transport_mode == "高铁":
                return f"{from_location}→{to_location}：{info['distance']}公里，高铁约{info['train']}"
            if transport_mode == "飞机":
                return f"{from_location}→{to_location}：{info['distance']}公里，飞机约{info['flight']}"
            return (f"{from_location}→{to_location}：{info['distance']}公里，"
                    f"飞机约{info['flight']}，高铁约{info['train']}")

    # 查市内
    for (a, b), minutes in _INTRACITY.items():
        if {from_location, to_location} == {a, b}:
            return f"{from_location}→{to_location}：市内交通约{minutes}分钟"

    return f"{from_location}→{to_location}：预计市内交通约30分钟（估算，请预留充足时间）"
