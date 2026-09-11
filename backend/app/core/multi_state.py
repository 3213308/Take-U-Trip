# app/core/multi_state.py
"""多智能体 State — 在单 Agent 字段基础上增加角色协作字段"""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class MultiAgentState(TypedDict):
    # ===== 输入 / 消息 / 记忆（与 TravelState 对齐）=====
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    user_profile: dict
    memory_context: str
    tool_cache: dict

    # 循环控制
    iteration: int
    tool_trace: list[dict]

    # ===== 三角色协作字段 =====
    draft_itinerary: dict | None     # Planner 产出的初版行程
    budget_review: dict              # Budgeter 的确定性核算结果
    review_status: str               # Reviewer 裁决：approve / revise
    reviewer_feedback: str           # 打回时给 Planner 的修改指令
    review_round: int                # 已审查轮数（防死循环）
    final_itinerary: dict | None     # 定稿行程
    is_planning: bool                # Supervisor 分流：True=走多角色精修，False=直答快路径

    # ===== 输出（与单 Agent 输出对齐，兼容 API / save_memory）=====
    final_answer: str
    forced_stop: bool
    itinerary: dict | None

    intent: str  # "planning" / "non_planning"
    action: str  # "info_query" / "modify" / "chat"
    slots: dict  # 已提取槽位
    missing_slots: list  # 缺哪些必填槽位
    clarify_question: str  # 要 interrupt 的话

