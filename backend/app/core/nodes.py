# app/core/nodes.py
"""LangGraph 节点实现 — 每个节点是一个纯函数，输入 state，输出 state 的更新"""

import asyncio
import logging

from app.memory.cache import get_tool_cache, ToolCache
from app.memory.context_builder import build_memory_context
from app.memory.profile import extract_preferences
from app.memory.store import get_memory_store

from langchain_core.messages import AIMessage, ToolMessage

from app.config import get_settings
from app.llm.client import get_llm
from app.tools import get_all_tools, get_tool_map

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_TOOL_RETRIES = 2


def load_memory_node(state: dict) -> dict:
    """循环开始前：加载用户画像和历史行程，组装记忆上下文"""
    user_id = state.get("user_id", "default")
    store = get_memory_store()

    profile = store.get_profile(user_id)
    recent_trips = store.get_recent_itineraries(user_id)
    memory_context = build_memory_context(profile, recent_trips)

    logger.info("[load_memory] 用户=%s, 画像=%d字段, 历史行程=%d条",
                user_id, len(profile), len(recent_trips))

    return {
        "user_profile": profile,
        "memory_context": memory_context,
    }



async def agent_node(state: dict) -> dict:
    from langchain_core.messages import SystemMessage

    from app.core.mcp_manager import get_mcp_tools

    llm = get_llm()

    # 关键：本地工具 + MCP 工具合并，对模型来说它们完全等价
    local_tools = get_all_tools()
    mcp_tools = get_mcp_tools()
    all_tools = local_tools + mcp_tools
    llm_with_tools = llm.bind_tools(all_tools)

    memory_context = state.get("memory_context", "")
    system_content = (
        "你是智能旅游规划助手。\n"
        "规则：\n"
        "1. 用户询问'怎么去/哪个好/比较'时，必须对比查到的全部交通方式（高铁vs飞机），"
        "给出时间和价格对比后再推荐\n"
        "2. 用户只是闲聊或询问你的能力时，直接自然语言回答，不要调用工具、不要生成行程\n"
        "3. 只有用户明确表达旅行规划需求时，才收集信息并生成行程\n"
        "4. 本地工具和 mcp_ 前缀工具能力重叠时，优先调用 mcp_ 前缀的 MCP 工具\n"
    )
    if memory_context:
        system_content += f"\n\n{memory_context}"

    messages = [SystemMessage(content=system_content)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    iteration = state.get("iteration", 0) + 1

    logger.info(
        "[agent_node] 第%d轮，tool_calls=%d（本地%d+MCP%d）",
        iteration, len(response.tool_calls), len(local_tools), len(mcp_tools),
    )
    return {"messages": [response], "iteration": iteration}




async def tool_node(state: dict) -> dict:
    last_msg = state["messages"][-1]
    tool_calls = getattr(last_msg, "tool_calls", [])
    if not tool_calls:
        return {}

    from app.core.mcp_manager import get_mcp_tools

    tool_map = get_tool_map()
    tool_map = {**tool_map, **{t.name: t for t in get_mcp_tools()}}

    tool_trace = state.get("tool_trace", [])
    cache = get_tool_cache()

    async def execute_single(tc: dict) -> ToolMessage:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_id = tc["id"]

        # 先查缓存
        cache_key = ToolCache.make_key(tool_name, tool_args)
        cached = cache.get(cache_key)
        if cached is not None:
            tool_trace.append({"name": tool_name, "args": tool_args, "status": "cache_hit"})
            logger.info("[tool] 缓存命中: %s", tool_name)
            return ToolMessage(content=cached, tool_call_id=tool_id)

        tool = tool_map.get(tool_name)
        if tool is None:
            msg = f"未知工具: {tool_name}"
            tool_trace.append({"name": tool_name, "args": tool_args, "status": "unknown_tool"})
            return ToolMessage(content=msg, tool_call_id=tool_id)

        last_error = None
        for attempt in range(MAX_TOOL_RETRIES + 1):
            try:
                result = await tool.ainvoke(tool_args)
                result_str = result if isinstance(result, str) else str(result)
                cache.set(cache_key, result_str)  # 写入缓存
                tool_trace.append({"name": tool_name, "args": tool_args, "status": "ok"})
                return ToolMessage(content=result_str, tool_call_id=tool_id)
            except Exception as e:
                last_error = e
                if attempt < MAX_TOOL_RETRIES:
                    await asyncio.sleep(0.5 * (attempt + 1))

        msg = f"工具 {tool_name} 执行失败: {last_error}"
        tool_trace.append({"name": tool_name, "args": tool_args, "status": "failed"})
        return ToolMessage(content=msg, tool_call_id=tool_id)

    tool_messages = await asyncio.gather(*[execute_single(tc) for tc in tool_calls])
    return {"messages": tool_messages, "tool_trace": tool_trace}



def finalize_node(state: dict) -> dict:
    """最终输出节点 — 循环结束后提取最终答案"""
    last_msg = state["messages"][-1]
    final_answer = last_msg.content if last_msg.content else "（无回答）"

    forced_stop = state.get("iteration", 0) >= settings.MAX_ITERATIONS
    if forced_stop:
        logger.warning("[finalize] 达到最大迭代次数，强制结束")

    return {
        "final_answer": final_answer,
        "forced_stop": forced_stop,
    }


def should_continue(state: dict) -> str:
    """条件路由 — 决定继续循环还是结束

    返回值必须和 graph.add_conditional_edges 里定义的 key 对应。
    """
    last_msg = state["messages"][-1]
    tool_calls = getattr(last_msg, "tool_calls", [])
    iteration = state.get("iteration", 0)

    if tool_calls and iteration < settings.MAX_ITERATIONS:
        return "tools"       # 继续循环：去工具节点
    return "finalize_structured"        # 结束：去最终输出节点


# 强规划信号：订酒店/城际交通几乎必然是在做行程规划
# search_attractions/search_restaurants 单独出现只算信息查询
_PLANNING_TOOLS = {"search_hotels", "search_transport"}
_PLAN_KEYWORDS = ("规划", "行程", "旅游", "旅行", "游玩", "几日游", "日游", "安排", "攻略")


def finalize_structured_node(state: dict) -> dict:
    """结构化输出节点 — 带意图守卫

    防幻觉/防误触发：
    1. 闲聊/简单问答（没调规划工具且无规划关键词）→ 直接自然语言回答
    2. 行程规划意图 → with_structured_output 生成 Pydantic 行程
    """
    from langchain_core.messages import HumanMessage
    from app.models.itinerary import Itinerary

    # ===== 意图守卫：判断是否真的需要生成行程 =====
    called_tools = {t["name"] for t in state.get("tool_trace", [])}
    user_text = " ".join(
        m.content for m in state["messages"] if isinstance(m, HumanMessage)
    )
    has_planning_signal = bool(called_tools & _PLANNING_TOOLS) or any(
        kw in user_text for kw in _PLAN_KEYWORDS
    )

    last_ai_msg = state["messages"][-1]
    direct_answer = last_ai_msg.content or ""

    # 非规划意图：直接返回自然语言，不强行结构化
    if not has_planning_signal:
        logger.info("[finalize] 判定为非规划意图，直接输出文本（不生成行程）")
        return {"itinerary": None, "final_answer": direct_answer}

    # ===== 规划意图：结构化输出 =====
    llm = get_llm()
    structured_llm = llm.with_structured_output(Itinerary, method="function_calling")

    try:
        itinerary = structured_llm.invoke(state["messages"])
        itinerary_dict = itinerary.model_dump()
        logger.info(
            "[finalize_structured] 行程生成成功: %s %d天 预算%.0f",
            itinerary.destination, itinerary.days, itinerary.total_budget,
        )
        return {
            "itinerary": itinerary_dict,
            "final_answer": f"已生成{itinerary.destination}{itinerary.days}天行程",
        }
    except Exception as e:
        logger.exception("[finalize_structured] 结构化输出失败，降级为纯文本")
        return {"itinerary": None, "final_answer": direct_answer or f"行程生成失败: {e}"}


def save_memory_node(state: dict) -> dict:
    """行程生成后：保存行程 + 提取偏好更新画像"""
    from langchain_core.messages import HumanMessage

    user_id = state.get("user_id", "default")
    itinerary = state.get("itinerary")
    if not itinerary:
        return {}

    store = get_memory_store()
    store.save_itinerary(user_id, itinerary)

    # 提取用户原始消息（新增）
    user_msgs = [
        m.content for m in state["messages"]
        if isinstance(m, HumanMessage)
    ]
    user_text = " ".join(user_msgs)

    prefs = extract_preferences(itinerary, user_text)
    if prefs:
        store.merge_profile(user_id, prefs)

    logger.info("[save_memory] 记忆已保存: %s", user_id)
    return {}
