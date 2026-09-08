# app/core/graph.py
"""LangGraph 图构建 — 加入记忆节点"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.core.nodes import (
    agent_node,
    finalize_structured_node,
    load_memory_node,
    save_memory_node,
    should_continue,
    tool_node,
)
from app.core.state import TravelState


def build_graph():
    memory = MemorySaver()
    builder = StateGraph(TravelState)

    builder.add_node("load_memory", load_memory_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("finalize_structured", finalize_structured_node)
    builder.add_node("save_memory", save_memory_node)

    # 流程：加载记忆 → agent 循环 → 结构化输出 → 保存记忆
    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "agent")
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "finalize_structured": "finalize_structured"},
    )
    builder.add_edge("tools", "agent")
    builder.add_edge("finalize_structured", "save_memory")
    builder.add_edge("save_memory", END)

    return builder.compile(checkpointer=memory)


travel_graph = build_graph()
