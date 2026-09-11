# app/tools/route.py
import logging
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from app.adapters.real.route import AmapRouteAdapter
from app.config import get_settings

logger = logging.getLogger(__name__)

class CalculateRouteInput(BaseModel):
    from_location: str
    to_location: str
    city: str = Field(default="", description="所在城市")
    transport_mode: str = "auto"

@tool(args_schema=CalculateRouteInput)
async def calculate_route(from_location: str, to_location: str,
                          city: str = "", transport_mode: str = "auto") -> str:
    """计算两点间驾车时间和距离，用于安排行程时间衔接。
    计算两个地点之间的驾车时间和距离。
    当安排一天内多个景点/餐厅/酒店的行程衔接时必须调用，
    用来判断两个活动之间需要留多少交通时间。
    例：宽窄巷子→锦里古街需要多久，熊猫基地→春熙路需要多久。
    """
    try:
        adapter = AmapRouteAdapter(get_settings().AMAP_API_KEY)
        result = await adapter.calculate(city or "北京", from_location, to_location)
        note = f"（{result['note']}）" if result["note"] else ""
        return (f"{from_location}→{to_location}：驾车约{result['minutes']}分钟，"
                f"{result['distance_km']}公里{note}")
    except Exception as e:
        logger.exception("路线计算异常")
        return f"{from_location}→{to_location}：预计市内交通约30分钟（估算）"
