# app/core/multi_graph.py
"""多智能体 Supervisor 图

流程：
  load_memory → planner → budgeter → reviewer
      ↑                                  │
      └──────── 打回（revise 且未达上限）──┘
                                   approve/达上限 → finalize_multi → save_memory → END
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.core.multi_nodes import (
    MAX_REVIEW_ROUNDS,
    budgeter_node,
    finalize_direct_node,
    finalize_multi_node,
    planner_node,
    reviewer_node,
)
from app.core.multi_state import MultiAgentState
from app.core.nodes import load_memory_node, save_memory_node


def route_after_planner(state: dict) -> str:
    """Supervisor 分流：规划→多角色精修；非规划→直答快路径"""
    return "budgeter" if state.get("is_planning") else "finalize_direct"


def route_after_review(state: dict) -> str:
    """审核后的条件路由：还能打回就回 Planner，否则定稿

    返回值必须和 add_conditional_edges 的映射 key 完全一致。
    """
    status = state.get("review_status", "")
    review_round = state.get("review_round", 0)

    if status == "revise" and review_round < MAX_REVIEW_ROUNDS:
        return "planner"            # 打回，Planner 带着 feedback 重做
    return "finalize_multi"         # approve 通过，或达到上限强制放行


def build_multi_agent_graph():
    builder = StateGraph(MultiAgentState)

    # 复用单 Agent 的记忆加载/保存节点，不重复造轮子
    builder.add_node("load_memory", load_memory_node)
    builder.add_node("planner", planner_node)
    builder.add_node("budgeter", budgeter_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("finalize_multi", finalize_multi_node)
    builder.add_node("finalize_direct", finalize_direct_node)
    builder.add_node("save_memory", save_memory_node)

    # 线性主干
    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "planner")

    # Planner 后第一次分叉：规划 vs 直答
    builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {"budgeter": "budgeter", "finalize_direct": "finalize_direct"},
    )

    builder.add_edge("budgeter", "reviewer")

    # Reviewer 后第二次分叉：打回 vs 定稿
    builder.add_conditional_edges(
        "reviewer",
        route_after_review,
        {"planner": "planner", "finalize_multi": "finalize_multi"},
    )

    builder.add_edge("finalize_multi", "save_memory")
    builder.add_edge("finalize_direct", "save_memory")
    builder.add_edge("save_memory", END)

    return builder.compile(checkpointer=MemorySaver())


multi_agent_graph = build_multi_agent_graph()
