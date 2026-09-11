# app/core/multi_graph.py
"""多智能体 Supervisor 图"""

from pathlib import Path
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.core.multi_nodes import (
    MAX_REVIEW_ROUNDS,
    budgeter_node,
    finalize_multi_node,
    planner_node,
    reviewer_node,
    intake_node,
    answer_node,
    modify_node,
)
from app.core.multi_state import MultiAgentState
from app.core.nodes import load_memory_node, save_memory_node

import aiosqlite

def route_after_intake(state: dict) -> str:
    intent = state.get("intent", "non_planning")
    action = state.get("action", "chat")
    missing = state.get("missing_slots", [])
    if intent == "planning" and missing:
        return "answer"
    if intent == "planning":
        return "planner"
    if action == "modify":
        return "modify"
    return "answer"


def route_after_review(state: dict) -> str:
    status = state.get("review_status", "")
    review_round = state.get("review_round", 0)
    if status == "revise" and review_round < MAX_REVIEW_ROUNDS:
        return "planner"
    return "finalize_multi"


_checkpoints_db = Path(__file__).resolve().parent.parent.parent / "checkpoints.db"
_graph = None
_saver = None


async def get_multi_agent_graph():
    global _graph, _saver
    if _graph is None:
        conn = await aiosqlite.connect(str(_checkpoints_db))
        _saver = AsyncSqliteSaver(conn)
        await _saver.setup()
        builder = StateGraph(MultiAgentState)
        builder.add_node("load_memory", load_memory_node)
        builder.add_node("intake", intake_node)
        builder.add_node("planner", planner_node)
        builder.add_node("budgeter", budgeter_node)
        builder.add_node("reviewer", reviewer_node)
        builder.add_node("finalize_multi", finalize_multi_node)
        builder.add_node("answer", answer_node)
        builder.add_node("save_memory", save_memory_node)
        builder.add_node("modify", modify_node)

        builder.add_edge(START, "load_memory")
        builder.add_edge("load_memory", "intake")
        builder.add_conditional_edges("intake", route_after_intake, {
            "planner": "planner", "answer": "answer","modify": "modify"
        })
        builder.add_edge("planner", "budgeter")
        builder.add_edge("modify", "budgeter")
        builder.add_edge("budgeter", "reviewer")
        builder.add_conditional_edges("reviewer", route_after_review, {
            "planner": "planner", "finalize_multi": "finalize_multi",
        })
        builder.add_edge("finalize_multi", "save_memory")
        builder.add_edge("answer", "save_memory")
        builder.add_edge("save_memory", END)

        _graph = builder.compile(checkpointer=_saver)
    return _graph
