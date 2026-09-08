# app/core/state.py
"""LangGraph State 定义"""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TravelState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

    # 循环控制
    iteration: int
    tool_trace: list[dict]

    # 最终输出
    final_answer: str
    forced_stop: bool
    itinerary: dict | None

    # 记忆（新增）
    user_id: str               # 用户标识
    user_profile: dict         # 用户画像
    memory_context: str        # 注入 prompt 的记忆摘要
    tool_cache: dict           # 工具缓存
