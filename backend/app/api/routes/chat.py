# app/api/routes/chat.py
"""聊天接口 — SSE 流式输出 Agent 执行过程

SSE 事件类型：
- status:       阶段状态（memory_loaded / planner_done / budgeter_done / reviewer_done / finalizing）
- tool_result:  工具调用结果（含 name/args/status）
- final:        最终结果（answer + itinerary + forced_stop）
- error:        错误
- done:         流结束

"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.api.schemas import ChatRequest
from app.core.multi_graph import get_multi_agent_graph
from app.core.multi_state import MultiAgentState



logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sse(event: str, data: dict) -> str:
    """格式化为 SSE 协议文本"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_agent(req: ChatRequest, thread_id: str):
    """核心：用 LangGraph astream 逐节点流式产出"""
    initial_state: MultiAgentState = {
        "messages": [HumanMessage(content=req.message)],
        "user_id": req.user_id,
        "iteration": 0,
        "tool_trace": [],
        "final_answer": "",
        "forced_stop": False,
        "itinerary": None,
        "user_profile": {},
        "memory_context": "",
        "tool_cache": {},
        # ===== 多 Agent 协作字段（新增）=====
        "draft_itinerary": None,
        "budget_review": {},
        "review_status": "",
        "reviewer_feedback": "",
        "review_round": 0,
        "final_itinerary": None,
        "is_planning": False,
        # intake 新字段
        "intent": "",
        "action": "",
        "slots": {},
        "missing_slots": [],
        "clarify_question": "",

    }

    config = {"configurable": {"thread_id": thread_id}}

    # 记录已发送过的工具，避免重复推送
    last_trace_len = 0

    try:
        # stream_mode="updates"：每个节点执行完后产出 {节点名: 状态更新}
        graph = await get_multi_agent_graph()
        async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):

            for node_name, node_update in chunk.items():
                if not node_update:
                    continue

                # 记忆加载
                if node_name == "load_memory":
                    profile = node_update.get("user_profile", {})
                    yield _sse("status", {
                        "phase": "memory_loaded",
                        "profile_fields": len(profile),
                    })


                # intake：意图判定
                elif node_name == "intake":
                    yield _sse("status", {
                        "phase": "intake_done",
                        "intent": node_update.get("intent", ""),
                        "action": node_update.get("action", ""),
                    })

                # answer：轻量回复（非规划路径）
                elif node_name == "answer":
                    trace = node_update.get("tool_trace", [])
                    for t in trace[last_trace_len:]:
                        yield _sse("tool_result", t)
                    last_trace_len = len(trace)
                    yield _sse("status", {"phase": "answer_done"})



                # Planner：推本轮新增的工具调用 + 完成状态
                elif node_name == "planner":
                    trace = node_update.get("tool_trace", [])
                    for t in trace[last_trace_len:]:
                        yield _sse("tool_result", t)
                    last_trace_len = len(trace)
                    yield _sse("status", {
                        "phase": "planner_done",
                        "round": node_update.get("review_round", 0),
                        "is_planning": node_update.get("is_planning", True),
                        "tool_count": len(trace),
                    })

                # Budgeter：确定性核算结果
                elif node_name == "budgeter":
                    br = node_update.get("budget_review", {})
                    yield _sse("status", {
                        "phase": "budgeter_done",
                        "actual_total": br.get("actual_total"),
                        "user_budget": br.get("user_budget"),
                        "remaining": br.get("remaining"),
                    })

                # Reviewer：裁决结果（approve / revise 打回）
                elif node_name == "reviewer":
                    yield _sse("status", {
                        "phase": "reviewer_done",
                        "decision": node_update.get("review_status"),
                        "round": node_update.get("review_round"),
                    })

                # 定稿
                elif node_name in ("finalize_multi", "finalize_direct"):
                    yield _sse("status", {"phase": "finalizing"})

            # 心跳
            yield ": heartbeat\n\n"
            await asyncio.sleep(0)

        # 最终结果：从 state 获取完整状态
        final_state = await graph.aget_state(config)

        values = final_state.values

        yield _sse("final", {
            "answer": values.get("final_answer", ""),
            "itinerary": values.get("itinerary"),
            "tool_trace": values.get("tool_trace", []),
            "forced_stop": values.get("forced_stop", False),
            "is_planning": values.get("is_planning", False),
        })

        yield _sse("done", {"thread_id": thread_id})

    except Exception as e:
        logger.exception("SSE 流异常")
        yield _sse("error", {"message": str(e)})


@router.post("/stream")
async def stream_chat(req: ChatRequest):
    """SSE 流式聊天接口"""
    thread_id = req.thread_id or f"thread-{uuid.uuid4().hex[:12]}"
    logger.info("SSE 请求: user=%s, thread=%s, msg=%s", req.user_id, thread_id, req.message[:50])

    return StreamingResponse(
        _stream_agent(req, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲，保证实时性
        },
    )


@router.post("/sync")
async def sync_chat(req: ChatRequest):
    """普通同步接口（非流式，用于简单场景和测试）"""
    thread_id = req.thread_id or f"thread-{uuid.uuid4().hex[:12]}"
    initial_state: MultiAgentState = {
        "messages": [HumanMessage(content=req.message)],
        "user_id": req.user_id,
        "iteration": 0,
        "tool_trace": [],
        "final_answer": "",
        "forced_stop": False,
        "itinerary": None,
        "user_profile": {},
        "memory_context": "",
        "tool_cache": {},
        # ===== 多 Agent 协作字段 =====
        "draft_itinerary": None,
        "budget_review": {},
        "review_status": "",
        "reviewer_feedback": "",
        "review_round": 0,
        "final_itinerary": None,
        "is_planning": False,
        # intake 新字段
        "intent": "",
        "action": "",
        "slots": {},
        "missing_slots": [],
        "clarify_question": "",

    }

    graph = await get_multi_agent_graph()
    result = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "thread_id": thread_id,
        "answer": result["final_answer"],
        "itinerary": result.get("itinerary"),
        "tool_trace": result.get("tool_trace", []),
    }


@router.get("/history")
async def chat_history(thread_id: str):
    """从 checkpoint 读取指定 thread 的聊天历史"""
    graph = await get_multi_agent_graph()
    state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    messages = state.values.get("messages", [])
    result = []
    for m in messages:
        role = "user" if m.type == "human" else "assistant"
        content = m.content if isinstance(m.content, str) else str(m.content)
        result.append({"role": role, "content": content})
    return {"thread_id": thread_id, "messages": result}
