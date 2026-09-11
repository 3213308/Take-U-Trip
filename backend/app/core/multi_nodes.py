# app/core/multi_nodes.py
"""多智能体节点：Planner（规划）→ Budgeter（确定性核算）→ Reviewer（独立审查）"""

import asyncio
import json
import logging
import re
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate

from app.memory.cache import ToolCache, get_tool_cache
from app.memory.store import get_memory_store
from app.models.itinerary import Itinerary
from app.models.review import ReviewResult
from app.tools import get_all_tools, get_tool_map

from app.llm.client import get_llm
from app.models.intention import IntentionResult, NonPlanningAction

import logging

from app.core.now import date_hint

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = f"""你是资深旅游规划师。根据用户需求，通过调用工具收集真实信息（天气、景点、酒店、餐厅、交通），然后规划出合理的多日行程。

{date_hint()}

工作原则：
1. 必须调用工具获取真实数据，禁止凭记忆编造景点价格、酒店价格、车次信息。
   工具分工：天气用 mcp_get_weather、景点用 mcp_search_attractions（这两个走 MCP）；
   酒店 search_hotels、餐厅 search_restaurants、交通 search_transport、路线 calculate_route 为本地工具。
2. 每个活动要有明确的时间、地点、费用
3. 【地理聚集】同一天的活动必须集中在同一个区域，不要跨城或跨区跑。
   例如：成都"锦里-武侯祠-宽窄巷子"在同一片区排一天，"熊猫基地-东郊记忆"另一天。
   选景点时优先选同一行政区/同一商圈的，不要全市乱跑。
4. 【排序原则】景点排序按游玩价值和评分：优先选评分4.5以上、知名度高的。
   从工具返回的列表里挑评分最高的前3-5个，不要全选。
5. 行程要考虑交通时间，不要把相距很远的活动排在一起
6. 预算要合理，不要超支
7. 如果用户没给出发城市，不要编造大交通，在 warnings 里提示即可
8. 行程要松紧适度，不要把一天排满（每天3-5个活动即可）
9. 住宿必须作为一个 category='住宿' 的活动放在行程里（通常在第一天晚上入住），
   cost=每晚房费×晚数。不要只在 warnings 里提酒店，必须在 activities 里加住宿活动
10. location 字段必须填具体可在地图上搜索的地点名（如"武侯祠"、"宽窄巷子"），
   禁止填"午餐"、"返回酒店"、"自由活动"等模糊词。在生成计划时，一定要能在地图上找到标志点。
   【坐标强制】每个"景点/餐饮/住宿"活动，都必须来自 mcp_search_attractions/search_restaurants/search_hotels 的工具返回，
   并把工具结果里的"坐标：lng,lat"（如"104.055,30.663"）逗号前数字填到 lng、逗号后填到 lat，一个都不能漏。
   不允许凭记忆写一个工具没返回的景点（那样没有坐标、地图无法精准定位）。
   只有"交通"类活动（如乘高铁、返程）允许没有坐标，前端会自动定位到目的地城市中心。
   坐标格式：lng 是经度（中国约73-135），lat 是纬度（约3-54）。
11. 同一天内两个活动地点之间，必须用 calculate_route 查交通时间，把交通时间排进行程，不能假设两个地方走路就到
12. 调用 transport/weather 工具时，日期必须是未来的真实日期（基于上面的"今天"推算），禁止用 2025-10-01 等示例日期
13. 【禁止重复】同一个景点在整个行程里只安排一次，不得在同一天或不同天重复出现；
    同一天内也不要安排两个名称或地点相同的活动。住宿（每晚）、每日三餐、往返交通属于正常重复，不受此限。


最终你需要输出结构化的 Itinerary，包含：
- destination: 目的地城市
- days: 天数
- total_budget: 用户预算
- days_plan: 每天的主题和活动列表（每个活动有时间、名称、地点、费用、类别）
- warnings: 需要用户确认的事项
"""


MAX_PLANNER_ITERS = 6    # Planner 节点内工具小循环上限
MAX_REVIEW_ROUNDS = 2    # Reviewer 最多打回次数（防死循环）
MAX_TOOL_RETRIES = 2



def _sanitize_for_structured(messages: list) -> list:
    """把工具循环历史拍平成纯文本对话，供结构化输出使用

    with_structured_output(function_calling) 只绑定了 Itinerary 一个工具。
    若历史残留业务工具的 AIMessage.tool_calls / ToolMessage，模型可能模仿
    历史继续输出业务工具调用，导致解析器报 Unknown tool type。
    这里统一转成 system/human 纯文本，让模型唯一能调用的 function 只剩 Itinerary。
    """
    cleaned: list = []
    for m in messages:
        kind = getattr(m, "type", "")
        if kind == "system":
            cleaned.append(SystemMessage(content=m.content))
        elif kind == "human":
            cleaned.append(HumanMessage(content=m.content))
        elif kind == "ai":
            # 纯 tool_call 的 AI 消息 content 通常为空，直接丢弃；其结果在工具结果里
            text = m.content if isinstance(m.content, str) else str(m.content)
            if text and text.strip():
                cleaned.append(HumanMessage(content=f"[规划过程记录] {text}"))
        elif kind == "tool":
            cleaned.append(HumanMessage(content=f"[工具查询结果] {m.content}"))
    return cleaned




async def planner_node(state: dict) -> dict:
    """规划师：节点内部完成 ReAct 工具小循环，再结构化输出初版行程

    设计要点：
    - 顶层图里 Planner 只是一个节点；agent↔tool 的多轮在节点内部闭环，
      这样顶层图的流转单位是"角色"，而不是单条消息。
    - 被 Reviewer 打回时，feedback 进上下文做针对性修改，不从零重写。
    - 内部新产生的消息回写 state.messages，Reviewer 才能提取工具证据。
    """
    llm = get_llm()
    from app.core.mcp_manager import get_mcp_tools
    mcp_tools = get_mcp_tools()
    # 机制隔离：预算汇总是 Budgeter 职责，Planner 不绑定 calculate_budget
    # 架构分层：天气、景点统一走 MCP（mcp_get_weather/mcp_search_attractions），
    # 不再绑定同名本地工具，避免 LLM 在两套重复工具间随机选择、导致 MCP 形同虚设。
    # 酒店/餐厅/路线/交通仍是本地函数（计算类/暂未 MCP 化的能力）。
    _LOCAL_SKIP = {"calculate_budget", "get_weather", "search_attractions"}
    planner_tools = [t for t in get_all_tools() if t.name not in _LOCAL_SKIP] + mcp_tools
    # dispatch map 只含"本次实际绑定"的工具——否则 LLM 即使没被绑定，
    # 也可能因 prompt 里出现过旧工具名而吐出该名字，tool_map 若含本地工具就会照样执行。
    tool_map = {t.name: t for t in planner_tools}
    # 兼容兜底：模型若习惯性吐出旧本地名，重定向到对应 MCP 工具（而不是执行本地实现）
    _MCP_ALIAS = {"get_weather": "mcp_get_weather", "search_attractions": "mcp_search_attractions"}
    bound = llm.bind_tools(planner_tools)
    cache = get_tool_cache()

    feedback = state.get("reviewer_feedback", "")
    prev_draft = state.get("draft_itinerary")
    is_redraft = bool(feedback)

    # 历史消息只用于本次推理，不重复回写；只回写本轮新建的消息
    context: list = [SystemMessage(content=PLANNER_SYSTEM_PROMPT)]
    memory_context = state.get("memory_context", "")
    if memory_context:
        context.append(SystemMessage(content=f"【用户画像与历史偏好】\n{memory_context}"))

    if is_redraft:

        # 重做不带第一轮的工具结果与 ReAct 过程：那些长 JSON 已凝结进 prev_draft。
        # 重做只需用户原话 + 上一版行程 + 审核意见；需补证据就按意见重新调工具（走 tool_cache）。
        context.extend([
            HumanMessage(content=m.content)
            for m in state["messages"]
            if getattr(m, "type", "") == "human"
        ])
    else:
        context.extend(state["messages"])

    new_messages: list = []
    if is_redraft:
        # 区分是 Reviewer 打回还是用户 modify
        is_user_modify = state.get("review_status") == "revise" and "【用户要求调整】" in feedback
        if is_user_modify:
            fb = HumanMessage(content=(
                "用户对你上一版行程提出了调整意见。这是局部修改，不是重新规划！\n"
                "\n"
                "严格规则：\n"
                "1. 除了用户明确要求换掉的那个活动，其他所有活动、时间、费用、酒店、餐厅必须原样复制到新行程中，一字不改\n"
                "2. 只调用工具查找替代那个被换掉的活动（如查景点/餐厅），不要重新查天气、酒店、交通\n"
                "3. 不要重新规划整个行程结构，天数、目的地、预算不变\n"
                "4. 新行程 = 旧行程的完整副本，只替换用户点名要换的那个活动\n"
                "\n"
                f"【上一版完整行程】\n{json.dumps(prev_draft, ensure_ascii=False) if prev_draft else '（无）'}\n\n"
                f"【用户调整意见】\n{feedback}"
            ))
        else:
            fb = HumanMessage(content=(
                "上一版行程未通过审核。下面先给出【上一版完整行程】，"
                "请在它基础上做最小修改：只改审核意见点名的问题，"
                "其余活动、时间、费用一律原样保留，严禁删除或清零未被点名的费用项（尤其是每晚住宿）。\n\n"
                f"【上一版完整行程】\n{json.dumps(prev_draft, ensure_ascii=False) if prev_draft else '（无）'}\n\n"
                f"【审核意见】\n{feedback}"
            ))
        context.append(fb)
        new_messages.append(fb)

        logger.info("[Planner] 第%d次重做，携带审核反馈与上一版行程", state.get("review_round", 0))

    tool_trace = list(state.get("tool_trace", []))

    def _normalize_tool_result(result) -> str:
        """本地工具返回 str；MCP 工具经 langchain-mcp-adapters 返回内容块列表
        （[{'type':'text','text':...}] 或 TextContent 对象），统一抽成纯文本。"""
        if isinstance(result, str):
            return result
        # MCP 内容块列表：拼接所有 text 段
        if isinstance(result, list):
            texts = []
            for block in result:
                if isinstance(block, dict):
                    t = block.get("text")
                else:
                    t = getattr(block, "text", None)
                if t:
                    texts.append(str(t))
            if texts:
                return "\n".join(texts)
        return str(result)

    def _summarize_tool_result(name: str, result_str: str, max_lines: int = 5) -> str:
        """工具结果摘要：超过 max_lines 行时截断，保留前 max_lines-1 行 + 剩余条数提示"""
        lines = result_str.split("\n")
        if len(lines) <= max_lines:
            return result_str
        kept = lines[:max_lines - 1]
        omitted = len(lines) - max_lines
        kept.append(f"... 另有{omitted}条结果省略，如需查看请重新搜索指定类别")
        return "\n".join(kept)


    # 工具失败降级策略：告诉 LLM 遇到工具挂了该怎么办，不要返回原始错误堆栈
    _FALLBACKS = {
        "get_weather": "天气查询暂时不可用。请基于常识给出穿衣建议，并在 warnings 里标注'天气数据未能获取，请用户自行确认天气'。",
        "mcp_get_weather": "天气查询暂时不可用。请基于常识给出穿衣建议，并在 warnings 里标注'天气数据未能获取，请用户自行确认天气'。",
        "search_attractions": "景点搜索暂时不可用。请基于常识推荐2-3个知名景点，在 warnings 里标注'景点数据未能获取，请用户自行核实开放时间和票价'。",
        "mcp_search_attractions": "景点搜索暂时不可用。请基于常识推荐2-3个知名景点，在 warnings 里标注'景点数据未能获取，请用户自行核实开放时间和票价'。",
        "search_hotels": "酒店搜索暂时不可用。请推荐2个连锁酒店品牌作为占位，在 warnings 里标注'酒店数据未能获取，请用户自行预订'。",
        "search_restaurants": "餐厅搜索暂时不可用。请推荐2-3个当地知名菜系或品牌餐厅，在 warnings 里标注'餐厅数据未能获取，请用户自行核实'。",
        "search_transport": "交通查询暂时不可用。请在 warnings 里提示用户自行查询高铁/航班，不要编造车次和价格。",
        "calculate_route": "路线计算暂时不可用。请按'相邻景点打车约15-30分钟'估算交通时间，不要编造精确距离。",
    }



    async def run_one_tool(tc: dict) -> ToolMessage:
        """单个工具：缓存优先 → 重试 → 失败兜底，与单 Agent tool_node 同标准"""
        name, args, tc_id = tc["name"], tc["args"], tc["id"]
        # 旧本地名重定向到 MCP，并对齐参数签名（本地 get_weather 用 start_date，MCP 用 date）
        if name in _MCP_ALIAS:
            logger.info("[Planner] 工具名 %s 重定向到 %s（天气/景点统一走 MCP）", name, _MCP_ALIAS[name])
            name = _MCP_ALIAS[name]
            if name == "mcp_get_weather" and "date" not in args:
                args = {**args, "date": args.get("start_date", "")}
                args.pop("start_date", None)
                args.pop("end_date", None)
        cache_key = ToolCache.make_key(name, args)
        cached = cache.get(cache_key)
        if cached is not None:
            summarized = _summarize_tool_result(name, cached)
            tool_trace.append({"name": name, "args": args, "status": "cache_hit"})
            return ToolMessage(content=cached, tool_call_id=tc_id)

        tool = tool_map.get(name)
        if tool is None:
            tool_trace.append({"name": name, "args": args, "status": "unknown_tool"})
            return ToolMessage(content=f"未知工具: {name}", tool_call_id=tc_id)

        last_error = None
        for attempt in range(MAX_TOOL_RETRIES + 1):
            try:
                logger.info("[Planner] 执行工具 %s args=%s", name, args)
                result = await tool.ainvoke(args)
                result_str = _normalize_tool_result(result)
                result_str = _summarize_tool_result(name, result_str)
                cache.set(cache_key, result_str)
                tool_trace.append({"name": name, "args": args, "status": "ok"})
                return ToolMessage(content=result_str, tool_call_id=tc_id)

            except Exception as e:
                last_error = e
                if attempt < MAX_TOOL_RETRIES:
                    await asyncio.sleep(0.5 * (attempt + 1))

        tool_trace.append({"name": name, "args": args, "status": "failed"})
        return ToolMessage(content=f"工具 {name} 执行失败: {last_error}", tool_call_id=tc_id)

    # ===== 节点内 ReAct 工具小循环 =====
    stopped_naturally = False
    for _ in range(MAX_PLANNER_ITERS):
        ai_msg: AIMessage = await bound.ainvoke(context)
        context.append(ai_msg)
        new_messages.append(ai_msg)

        if not ai_msg.tool_calls:
            stopped_naturally = True
            break
        tool_msgs = await asyncio.gather(*[run_one_tool(tc) for tc in ai_msg.tool_calls])
        context.extend(tool_msgs)
        new_messages.extend(tool_msgs)

    if not stopped_naturally:
        logger.warning("[Planner] 达到内部循环上限%d，强制进入结构化", MAX_PLANNER_ITERS)

    # ===== 规划意图：结构化生成初版行程（先清洗业务工具协议，避免污染 Itinerary 解析）=====
    structured_llm = llm.with_structured_output(Itinerary, method="function_calling")
    clean_context = _sanitize_for_structured(context)
    clean_context.append(HumanMessage(content=(
        "以上是用户需求和全部工具查询结果。现在只输出符合 Itinerary 结构的完整行程，"
        "不要调用任何其他工具。"
    )))

    # 注意：function_calling 解析器在模型没正确发起 Itinerary 调用时会返回 None（不抛异常），
    # 所以"抛异常"和"返回 None"都要视为结构化失败。
    draft_model: Itinerary | None = None
    first_error: Exception | None = None
    try:
        draft_model = await structured_llm.ainvoke(clean_context)
    except Exception as e:
        first_error = e

    if draft_model is None:
        # 兜底重试：只保留系统约束 + 用户原话 + 工具结果，剔除规划过程噪声
        logger.warning("[Planner] 结构化首次未产出(%s)，最小上下文重试一次", first_error)
        minimal = [SystemMessage(content=PLANNER_SYSTEM_PROMPT)]
        minimal += _sanitize_for_structured([
            m for m in context if getattr(m, "type", "") in ("human", "tool")
        ])
        minimal.append(HumanMessage(content="请只输出 Itinerary 结构化行程，禁止调用其他工具。"))
        try:
            draft_model = await structured_llm.ainvoke(minimal)
        except Exception as e2:
            logger.error("[Planner] 结构化重试仍失败: %s", e2)
            draft_model = None

    if draft_model is None:
        # 两次都拿不到：重做轮回退到上一版（至少不丢已通过部分），初版无旧稿可退才抛错
        if prev_draft:
            logger.error("[Planner] 两次结构化均失败，回退到上一版行程")
            draft = dict(prev_draft)
        else:
            raise RuntimeError("Planner 结构化两次失败，且无上一版行程可回退") from first_error
    else:
        draft = draft_model.model_dump()
        draft = dedup_activities(draft)

    logger.info(
        "[Planner] 初版行程完成: %s %d天, 累计工具轨迹%d条",
        draft.get("destination"), draft.get("days"), len(tool_trace),
    )

    return {
        "messages": new_messages,
        "tool_trace": tool_trace,
        "is_planning": True,
        "draft_itinerary": draft,
        "reviewer_feedback": "",   # 反馈已消费，清空防止下轮误带
        "review_status": "",
    }




# ===== 费用类别 → Itinerary 分项字段映射 =====
_CATEGORY_TO_FIELD = {
    "交通": "transport_cost",
    "住宿": "accommodation_cost",
    "餐饮": "food_cost",
    "景点": "attraction_cost",
}


def _norm_place_text(s) -> str:
    """归一化地点/活动名：去空白与标点、转小写，用于判断是否同一活动"""
    return re.sub(r"[\s　，。、,.:：;；!！?？（）()【】\[\]\-—_|/\\]+", "", str(s or "")).lower()


def dedup_activities(draft: dict) -> dict:
    """确定性去除重复活动（不信任 LLM 一定不重复）。

    - 同一天内：同名活动、或同一"景点"落在同一地点的重复项，只保留第一条；
    - 跨天：同一个"景点"不应在不同日期重复游览，只保留首次出现那天；
    - 住宿（每晚回酒店）、餐饮（每日多餐）、交通属于合理重复，不做跨天去重。
    """
    if not draft or not draft.get("days_plan"):
        return draft
    seen_attr_global: set[str] = set()
    removed = 0
    for day in draft["days_plan"]:
        seen_day: set[tuple] = set()
        kept = []
        for act in day.get("activities", []):
            cat = act.get("category", "")
            name_key = _norm_place_text(act.get("name", ""))
            loc_key = _norm_place_text(act.get("location", ""))
            is_attr = cat == "景点"
            day_keys = [("n", name_key)]
            if is_attr and loc_key:
                day_keys.append(("l", loc_key))
            day_keys = [k for k in day_keys if k[1]]
            if any(k in seen_day for k in day_keys):  # 日内重复
                removed += 1
                continue
            if is_attr:  # 跨天重复景点
                gkey = name_key or loc_key
                if gkey and gkey in seen_attr_global:
                    removed += 1
                    continue
                if gkey:
                    seen_attr_global.add(gkey)
            seen_day.update(day_keys)
            kept.append(act)
        day["activities"] = kept
    if removed:
        logger.info("[Dedup] 已移除重复活动 %d 个", removed)
    return draft


def budgeter_node(state: dict) -> dict:
    """预算师：用确定性代码重算所有费用，不信任 Planner 填的数字

    职责（对准基线病灶：20%预算错算、晚数算错、daily_budget乱填）：
    1. 按天汇总活动费用，重算 daily_budget
    2. 按类别汇总四大分项，重算实际总花费
    3. 对比用户预算，判断是否超支
    全程不用 LLM —— 算术必须确定、可复算。
    """
    draft = state.get("draft_itinerary")
    if not draft:
        return {"budget_review": {"error": "无初版行程"}}

    # 拷贝一份再改，避免直接改 state 里的对象
    draft = {**draft, "days_plan": [
        {**day, "activities": list(day["activities"])}
        for day in draft["days_plan"]
    ]}

    # 1. 重算每日预算
    for day in draft["days_plan"]:
        day_total = round(sum(float(a.get("cost", 0)) for a in day["activities"]), 2)
        day["daily_budget"] = day_total

    # 2. 重算分项费用
    parts = {field: 0.0 for field in _CATEGORY_TO_FIELD.values()}
    for day in draft["days_plan"]:
        for act in day["activities"]:
            field = _CATEGORY_TO_FIELD.get(act.get("category"))
            if field:
                parts[field] += float(act.get("cost", 0))
    parts = {k: round(v, 2) for k, v in parts.items()}
    actual_total = round(sum(parts.values()), 2)

    # 3. 回填分项到行程（Planner 填的数字被权威覆盖）
    draft.update(parts)

    user_budget = float(draft.get("total_budget", 0))
    over = round(actual_total - user_budget, 2)

    budget_review = {
        "user_budget": user_budget,
        "actual_total": actual_total,
        "parts": parts,
        "is_over_budget": over > 0,
        "over_amount": max(over, 0),
        "remaining": round(user_budget - actual_total, 2),
    }
    logger.info(
        "[Budgeter] 实际花费%.0f / 用户预算%.0f（%s）",
        actual_total, user_budget,
        f"超支{over}" if over > 0 else f"剩余{user_budget - actual_total}",
    )
    return {"draft_itinerary": draft, "budget_review": budget_review}


async def reviewer_node(state: dict) -> dict:
    """审核员：对准三类基线病灶做独立审查，决定通过还是打回

    不调工具、不重排行程，只做"挑毛病"，保持与 Planner 的角色对立。
    """

    draft = state.get("draft_itinerary", {})
    budget_review = state.get("budget_review", {})
    review_round = state.get("review_round", 0) + 1

    # 工具证据：审查"无证据幻觉"的依据
    tool_evidence = "\n".join(
        getattr(m, "content", "")
        for m in state.get("messages", [])
        if getattr(m, "type", "") == "tool"
    )
    called_tools = sorted({t["name"] for t in state.get("tool_trace", [])})

    human_msgs = [m for m in state.get("messages", []) if getattr(m, "type", "") == "human"]
    user_text = human_msgs[-1].content if human_msgs else ""


    reviewer = get_llm()
    review_llm = reviewer.with_structured_output(ReviewResult, method="function_calling")

    prompt = SystemMessage(content=(
        "你是行程审核员，只拦截【硬伤】，不夸奖，也不要写逐项核对过程。\n"
        "只有下列情况才允许列为 severity=blocker（必须打回）：\n"
        "1. 费用错误或缺失：该有的费用大类缺失（如多日行程却没有住宿费）、"
        "加总错误、超出用户预算；\n"
        "2. 时间不可行：相邻活动时间冲突/倒流，或没留必要交通时间导致赶不上；\n"
        "3. 关键数字无工具证据：车次/航班、门票、酒店价格、人均消费在【工具证据】里找不到；\n"
        "4. 工具漏调：规划必需的工具没调（如多日行程没查酒店）。\n"
        "以下情况一律【不得】列为 blocker：已明确标注为'估算'的市内交通金额、"
        "措辞与表述优化、不影响可行性的松紧建议——确实要提就标 severity=minor。\n"
        "交通查询前提：只有【用户原始需求】明确给了出发城市/跨城/'怎么去'才要求查大交通，"
        "用户没给出发城市时只需在 warnings 提示待确认，不算漏调。\n"
        "feedback 里严禁罗列'XX一致/可接受/无问题'这类合格项，只写需要修改的 blocker 及具体动作。\n"
        "没有 blocker 时必须 decision=approve、issues 留空、feedback 留空。\n"
        f"本次实际调用工具：{called_tools}"
    ))
    user_msg = HumanMessage(content=(
        f"【用户原始需求】\n{user_text or '（无）'}\n\n"
        f"【待审行程】\n{json.dumps(draft, ensure_ascii=False)}\n\n"
        f"【预算核算】\n{json.dumps(budget_review, ensure_ascii=False)}\n\n"
        f"【工具证据】\n{tool_evidence[:4000] or '（无）'}"
    ))

    try:
        result: ReviewResult = await review_llm.ainvoke([prompt, user_msg])
    except Exception as e:
        # 审查器自身故障：fail-open 默认通过，避免审核节点把整条流程拖垮
        logger.warning("[Reviewer] 结构化审查失败，默认通过: %s", e)
        return {"review_round": review_round, "review_status": "approve", "reviewer_feedback": ""}

    # 确定性门控：是否打回只取决于有没有 blocker，不看模型自报的 decision
    # （模型可能 issues 留空却在 feedback 写小作文并自报 revise，必须用代码兜住）
    blockers = [i for i in result.issues if getattr(i, "severity", "blocker") != "minor"]
    decision = "revise" if blockers else "approve"
    feedback_text = result.feedback if decision == "revise" else ""

    logger.info(
        "[Reviewer] 第%d轮裁决=%s，问题%d个（其中blocker %d）",
        review_round, decision, len(result.issues), len(blockers),
    )

    return {
        "review_round": review_round,
        "review_status": decision,
        "reviewer_feedback": feedback_text,
        # 打回时清空 final，approve 时在 supervisor 里定稿
    }


def finalize_multi_node(state: dict) -> dict:
    """定稿：把 Budgeter 重算过的初版定为最终行程，并对齐下游字段

    - final_itinerary：多智能体产物
    - itinerary：同名写一份，兼容单 Agent 的 save_memory_node 和 API 层
    - 达到打回上限仍未通过时，强制放行并在 warnings 标注人工复核
    """
    draft = dict(state.get("draft_itinerary") or {})
    budget_review = state.get("budget_review", {}) or {}
    review_round = state.get("review_round", 0)
    status = state.get("review_status", "")

    warnings = list(draft.get("warnings", []))

    # 先判断是否"打回上限耗尽仍未通过"——这种情况不能给残次行程盖"核算通过"的章
    forced = status == "revise" and review_round >= MAX_REVIEW_ROUNDS

    # 1. 注入确定性预算结论（来自 Budgeter，不是 LLM 估计）
    if budget_review and not budget_review.get("error"):
        if forced:
            warnings.append(
                f"预算为机器加总约{budget_review['actual_total']}元，"
                f"但审查仍有未决问题，费用完整性需人工核对，不要直接采信"
            )
        elif budget_review.get("is_over_budget"):
            warnings.append(
                f"预算超支：实际花费约{budget_review['actual_total']}元，"
                f"超出{budget_review['over_amount']}元，建议降低住宿或餐饮标准"
            )
        else:
            warnings.append(
                f"预算核算通过：实际花费约{budget_review['actual_total']}元，"
                f"剩余{budget_review['remaining']}元"
            )

    # 2. 打回上限耗尽仍 revise → 强制放行
    if forced:
        warnings.append(f"经{review_round}轮修改仍有未决问题，已按当前最优版本定稿，建议人工复核")

    draft["warnings"] = warnings
    answer = f"已生成{draft.get('destination', '')}{draft.get('days', '')}天行程"

    logger.info("[finalize_multi] 定稿，审查%d轮，%s",
                review_round, "强制放行" if forced else "审核通过")

    return {
        "final_itinerary": draft,
        "itinerary": draft,          # 同名写一份，兼容单 Agent 的 save_memory_node 和 API 层
        "final_answer": answer,
        "forced_stop": forced,
        # 把最终回复写回 messages，下一轮同 thread_id 时 Planner 能看到自己上一轮说了什么
        "messages": [AIMessage(content=answer)],
    }



async def intake_node(state: dict) -> dict:
    """入口节点：LLM 判意图 + 提取槽位，不调业务工具"""
    INTAKE_SYSTEM_PROMPT = """你是旅游助手的意图路由器。分析用户这句话，输出：

    1. intent：
       - planning = 用户要完整多日行程规划（出现"X天/行程/规划/攻略/安排路线"等）
       - non_planning = 单点信息查询、美食/天气/景点推荐、闲聊、修改已有行程

    2. action（非规划时）：
       - info_query = 问天气/景点/美食/交通等单点信息，且不是在已有行程基础上调整
       - modify = 在已有行程基础上，对行程内容表达不满、想换掉某个景点、调整某天安排、
         嫌某天太赶/太松、不想去某个地方。即使没说"修改"两个字，只要针对已有行程提意见就是 modify
       - chat = 闲聊或问你能做什么


    3. slots：从用户话里提取的槽位
       planning 必填：destination（目的地城市）、days（天数）
       planning 可选：budget（预算）、start_city（出发城市）、date（出行日期）

    4. missing_slots：planning 意图必填但用户没说的槽位名
       例如用户说"帮我规划2天行程"但没说去哪 → missing_slots=["destination"]

    5. clarify_question：缺槽位时，用自然语言向用户提问，一次只问最关键的那个
       例如缺目的地："你想去哪个城市玩？"

    注意：
    - 用户只问"有什么好吃的/天气怎么样"→ non_planning + info_query，不是 planning
    - 在已有行程基础上，用户对某个景点表达不满（"不想去XX""XX太无聊了""能不能换一个"）
      → non_planning + modify，不是 info_query
    - 用户说"第二天太赶了"→ non_planning + modify
    - 槽位信息要从上下文推断，用户说"上次说的成都"也算 destination=成都
    - 已有行程时，用户提到的景点名如果出现在【当前已有行程】里，优先判 modify
    
    【判断示例】
    示例1：
    【已有行程】第1天: 长城、故宫；第2天: 颐和园、天坛
    用户消息：不想去长城，有没有别的好玩的
    输出：modify（对行程中的景点表达不满，想换掉）

    示例2：
    【已有行程】第1天: 长城、故宫；第2天: 颐和园、天坛
    用户消息：长城门票多少钱？
    输出：info_query（只是问单点信息，没有要改行程）

    示例3：
    【已有行程】第1天: 长城、故宫
    用户消息：第二天太赶了，能不能松一点
    输出：modify（对行程安排提意见）

    示例4：
    【已有行程】第1天: 长城、故宫
    用户消息：北京有什么火锅推荐？
    输出：info_query（跟行程无关的新查询）

    时间感知：""" + date_hint() + """
    """

    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentionResult, method="function_calling")

    # 组装用户消息：最后一条 human + 是否有已有行程
    human_msgs = [m for m in state["messages"] if getattr(m, "type", "") == "human"]
    user_text = human_msgs[-1].content if human_msgs else ""
    has_itinerary = bool(state.get("itinerary") or state.get("draft_itinerary"))

    # 兜底：checkpoint 丢了（重启），从 memory store 拿最近一次行程
    if not has_itinerary:
        store_itineraries = get_memory_store().get_recent_itineraries(state.get("user_id", "default"))
        if store_itineraries:
            latest = store_itineraries[-1]
            state["draft_itinerary"] = latest
            has_itinerary = True
            logger.info("[intake] checkpoint 无行程，从 memory store 加载最近行程: %s",
                        latest.get("destination", ""))

    user_msg = HumanMessage(content=(
        f"【用户消息】{user_text}\n\n"
        f"【当前会话是否已有行程】{'是' if has_itinerary else '否'}"
    ))

    # 如果有行程，把行程摘要带给 intake，让它知道行程里有什么
    if has_itinerary:
        itin = state.get("itinerary") or state.get("draft_itinerary") or {}
        days_summary = []
        for i, day in enumerate(itin.get("days_plan", []), 1):
            names = [a.get("name", "") for a in day.get("activities", [])]
            days_summary.append(f"第{i}天: {'、'.join(names)}")
        itinerary_brief = "\n".join(days_summary)
        user_msg = HumanMessage(content=(
            f"【用户消息】{user_text}\n\n"
            f"【当前已有行程】\n{itinerary_brief}"
        ))

    try:
        result: IntentionResult = await structured_llm.ainvoke([
            SystemMessage(content=INTAKE_SYSTEM_PROMPT),
            user_msg,
        ])
    except Exception as e:
        # LLM 自身故障：fail-open 走 chat，不让整条流程挂掉
        logger.warning("[intake] 意图解析失败，默认走 chat: %s", e)
        return {
            "intent": "non_planning",
            "action": "chat",
            "slots": {},
            "missing_slots": [],
            "clarify_question": "",
        }

    logger.info(
        "[intake] intent=%s action=%s slots=%s missing=%s",
        result.intent, result.action, result.slots, result.missing_slots,
    )

    result_dict = {
        "intent": result.intent.value,
        "action": result.action.value,
        "slots": result.slots,
        "missing_slots": result.missing_slots,
        "clarify_question": result.clarify_question,
    }

    # modify 意图：把用户修改意见塞进 reviewer_feedback，让 planner 走重做分支
    if result.action == NonPlanningAction.MODIFY:
        result_dict["reviewer_feedback"] = f"【用户要求调整】{user_text}"
        result_dict["review_status"] = "revise"
        logger.info("[intake] modify 意图，已将修改意见送入 planner 重做分支")

    return result_dict


async def answer_node(state: dict) -> dict:
    """非规划意图的轻量回复：按需调工具，不产出 Itinerary"""
    llm = get_llm()
    action = state.get("action", "chat")

    # 缺槽位：直接用 intake 生成的 clarify_question，不再调 LLM
    clarify = state.get("clarify_question", "")
    if clarify:
        logger.info("[answer] 缺槽位，直接回复澄清问题: %s", clarify)
        return {
            "final_answer": clarify,
            "messages": [AIMessage(content=clarify)],
            "tool_trace": list(state.get("tool_trace", [])),
            "is_planning": False,
            "draft_itinerary": None,
        }

    # 按 action 绑不同工具集
    from app.tools import get_all_tools
    all_tools = get_all_tools()
    tool_map = {t.name: t for t in all_tools}

    if action == "info_query":
        # 信息查询：只给查询类工具，不给 planner/budget
        allowed = [t for t in all_tools if t.name in (
            "search_restaurants", "get_weather",
            "search_attractions", "search_transport", "calculate_route",
        )]
    else:
        # chat：不绑工具
        allowed = []

    bound = llm.bind_tools(allowed) if allowed else llm

    messages = [SystemMessage(content=(
        "你是旅游助手。用户在问单点信息或闲聊，不要生成完整行程。"
        "需要查信息就调对应工具，查到后用简洁自然语言回答。"
        "如果用户只是闲聊，直接友好回复即可。"
        + date_hint()
    ))]
    # 带上用户原话和已有槽位
    human_msgs = [m for m in state["messages"] if getattr(m, "type", "") == "human"]
    messages.extend(human_msgs)
    if state.get("slots"):
        messages.append(SystemMessage(content=f"【已提取槽位】{state['slots']}"))

    # 轻量工具循环（最多 3 轮，不像 planner 那样 6 轮）
    tool_trace = list(state.get("tool_trace", []))
    for _ in range(3):
        resp = await bound.ainvoke(messages) if allowed else await llm.ainvoke(messages)
        messages.append(resp)
        if not getattr(resp, "tool_calls", None):
            break
        # 调工具（简化，复用 planner 的 run_one_tool 逻辑）
        tool_results = []
        for tc in resp.tool_calls:
            tool = tool_map.get(tc["name"])
            if tool:
                r = await tool.ainvoke(tc["args"])
                tool_trace.append({"name": tc["name"], "args": tc["args"], "status": "ok"})
                tool_results.append((str(r), tc["id"]))
        from langchain_core.messages import ToolMessage
        messages.extend([
            ToolMessage(content=c, tool_call_id=tid) for c, tid in tool_results
        ])

    answer_text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return {
        "final_answer": answer_text,
        "messages": [resp],   # 写回最后一条 AI 消息
        "tool_trace": tool_trace,
        "is_planning": False,
        "draft_itinerary": None,
    }


async def modify_node(state: dict) -> dict:
    """基于已有行程做局部修改，LLM 一次输出完整 JSON，不走工具循环"""
    llm = get_llm()
    user_msg = state["messages"][-1].content if state["messages"] else ""
    prev = state.get("final_itinerary") or state.get("itinerary")
    if not prev:
        store = get_memory_store()
        history = store.get_recent_itineraries(state.get("user_id", "default"), limit=1)

        if history:
            prev = history[0]  # history[0] 直接就是 itinerary dict
            logger.info("[modify] 从 memory store 加载最近行程: %s", prev.get("destination") if prev else None)

    if not prev:
        logger.warning("[modify] 没有已有行程，退回 planner")
        return {"draft_itinerary": None, "is_planning": True, "review_status": ""}

    try:
        resp = await llm.ainvoke([
            SystemMessage(content=(
                "你是行程修改助手。用户要求对已有行程做局部调整。\n"
                "规则：\n"
                "1. 除了用户明确要求修改的部分，其他所有活动、时间、费用必须原样复制，一字不改\n"
                "2. 不调用任何工具，直接输出完整修改后的行程 JSON\n"
                "3. JSON 格式与原行程完全一致：days_plan 数组，每天有 date/theme/daily_budget/activities\n"
                "4. activities 里每个活动必须有 time/name/location/category/cost 字段\n"
                "5. 新增的替代活动也要填完整字段，cost 估算即可\n"
                "直接输出 JSON，不要解释"
            )),
            HumanMessage(content=(
                f"【原有完整行程】\n{json.dumps(prev, ensure_ascii=False, indent=2)}\n\n"
                f"【用户修改要求】\n{user_msg}\n\n"
                f"请输出修改后的完整行程 JSON："
            )),
        ])
        content = resp.content if hasattr(resp, 'content') else str(resp)
        import re
        m = re.search(r'\{.*\}', content, re.DOTALL)
        if not m:
            logger.error("[modify] LLM 未返回 JSON")
            return {"draft_itinerary": None, "review_status": "", "reviewer_feedback": "modify 解析失败"}
        new_itinerary = json.loads(m.group())
        new_itinerary = dedup_activities(new_itinerary)
        logger.info("[modify] 局部修改完成: %s %s天",
                     new_itinerary.get("destination"), new_itinerary.get("days"))
        return {
            "draft_itinerary": new_itinerary,
            "is_planning": True,
            "review_status": "",
            "reviewer_feedback": "",
            "review_round": 0,
            "tool_trace": list(state.get("tool_trace", [])) + [{"name": "modify", "args": {"request": user_msg[:30]}, "status": "ok"}],
        }
    except Exception as e:
        logger.exception("[modify] 局部修改失败")
        return {"draft_itinerary": None, "review_status": "", "reviewer_feedback": f"modify 异常: {e}"}
