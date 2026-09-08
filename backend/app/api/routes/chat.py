# app/api/routes/chat.py
"""聊天接口 — SSE 流式输出 Agent 执行过程

SSE 事件类型：
- status:      阶段状态（加载记忆/思考中/生成行程）
- tool_call:   模型发起工具调用
- tool_result: 工具返回结果
- final:       最终行程（结构化 JSON）
- error:       错误
- done:        流结束
"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.api.schemas import ChatRequest
from app.core.graph import travel_graph
from app.core.state import TravelState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sse(event: str, data: dict) -> str:
    """格式化为 SSE 协议文本"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_agent(req: ChatRequest, thread_id: str):
    """核心：用 LangGraph astream 逐节点流式产出"""
    initial_state: TravelState = {
        "messages": [HumanMessage(content=req.message)],
        "iteration": 0,
        "tool_trace": [],
        "final_answer": "",
        "forced_stop": False,
        "itinerary": None,
        "user_id": req.user_id,
        "user_profile": {},
        "memory_context": "",
        "tool_cache": {},
    }
    config = {"configurable": {"thread_id": thread_id}}

    # 记录已发送过的工具，避免重复推送
    sent_tools: set[str] = set()
    last_trace_len = 0

    try:
        # stream_mode="updates"：每个节点执行完后产出 {节点名: 状态更新}
        async for chunk in travel_graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_update in chunk.items():
                if not node_update:
                    continue

                # 记忆加载阶段
                if node_name == "load_memory":
                    profile = node_update.get("user_profile", {})
                    yield _sse("status", {
                        "phase": "memory_loaded",
                        "profile_fields": len(profile),
                    })

                # agent 节点：检测新发起的工具调用
                if node_name == "agent":
                    msgs = node_update.get("messages", [])
                    for msg in msgs:
                        tool_calls = getattr(msg, "tool_calls", [])
                        for tc in tool_calls:
                            call_id = tc.get("id", str(uuid.uuid4()))
                            if call_id not in sent_tools:
                                sent_tools.add(call_id)
                                yield _sse("tool_call", {
                                    "name": tc["name"],
                                    "args": tc["args"],
                                })
                    yield _sse("status", {"phase": "thinking"})

                # tools 节点：推送工具结果
                if node_name == "tools":
                    trace = node_update.get("tool_trace", [])
                    for t in trace[last_trace_len:]:
                        yield _sse("tool_result", t)
                    last_trace_len = len(trace)

                # 结构化输出完成
                if node_name == "finalize_structured":
                    itinerary = node_update.get("itinerary")
                    if itinerary:
                        yield _sse("status", {"phase": "itinerary_ready"})

            # 心跳：防止代理超时断开
            yield ": heartbeat\n\n"
            await asyncio.sleep(0)

        # 最终结果：从 state 获取完整状态
        final_state = await travel_graph.aget_state(config)
        values = final_state.values

        yield _sse("final", {
            "answer": values.get("final_answer", ""),
            "itinerary": values.get("itinerary"),
            "tool_trace": values.get("tool_trace", []),
            "iteration": values.get("iteration", 0),
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
    initial_state: TravelState = {
        "messages": [HumanMessage(content=req.message)],
        "iteration": 0,
        "tool_trace": [],
        "final_answer": "",
        "forced_stop": False,
        "itinerary": None,
        "user_id": req.user_id,
        "user_profile": {},
        "memory_context": "",
        "tool_cache": {},
    }
    result = await travel_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "thread_id": thread_id,
        "answer": result["final_answer"],
        "itinerary": result.get("itinerary"),
        "tool_trace": result.get("tool_trace", []),
    }
