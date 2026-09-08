# app/core/multi_nodes.py
"""多智能体节点：Planner（规划）→ Budgeter（确定性核算）→ Reviewer（独立审查）"""

import asyncio
import json
import logging
import re
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.llm.client import get_llm
from app.memory.cache import ToolCache, get_tool_cache
from app.models.itinerary import Itinerary
from app.models.review import ReviewResult
from app.tools import get_all_tools, get_tool_map
# 复用单 Agent 的意图判定常量，保证单/多两套图的"规划意图"口径唯一
from app.core.nodes import _PLAN_KEYWORDS, _PLANNING_TOOLS

logger = logging.getLogger(__name__)

MAX_PLANNER_ITERS = 6    # Planner 节点内工具小循环上限
MAX_REVIEW_ROUNDS = 2    # Reviewer 最多打回次数（防死循环）
MAX_TOOL_RETRIES = 2


# 单点信息查询信号：用户只问某一类信息（吃/天气/能力/单点信息），不是要整份多日行程
# 命中这些且没有明确多日诉求时，即使模型越界调了 search_hotels，也判为直答
_DIRECT_INTENT_KEYWORDS = (
    "推荐一下", "有什么好吃", "好吃的", "火锅", "小吃", "美食", "餐厅", "餐馆",
    "天气", "气温", "穿什么",
    "你能做什么", "你是谁", "你会什么",
    "门票", "开放时间",
)
# 明确多日规划信号：出现具体天数，几乎必然要整份行程
_MULTI_DAY_PATTERN = re.compile(r"\d+\s*(天|日游)|[一二三四五六七八九十两]\s*天|几日游")


def _detect_planning_intent(user_text: str, called_tools: set[str]) -> tuple[bool, str]:
    """以用户文本为权威判定规划意图，工具调用仅在文本模糊时兜底。

    优先级：
    1. 文本含明确天数或强规划词（规划/行程/安排/攻略…）→ 规划
    2. 文本只问单点信息（美食/天气/能力…）且无多日诉求 → 直答，忽略越界工具
    3. 文本模糊时，才用"是否调用强规划工具"兜底
    返回 (是否规划, 判定原因)，原因写进日志便于排查。
    """
    text = (user_text or "").strip()
    has_multi_day = bool(_MULTI_DAY_PATTERN.search(text))
    has_plan_kw = any(kw in text for kw in _PLAN_KEYWORDS)
    has_direct_kw = any(kw in text for kw in _DIRECT_INTENT_KEYWORDS)

    # 1. 明确多日 / 强规划措辞 → 规划（"怎么去"这类单点词让位于明确天数）
    if has_multi_day or has_plan_kw:
        return True, f"文本含明确规划信号(多日={has_multi_day}, 规划词={has_plan_kw})"

    # 2. 单点信息查询 → 直答，不以模型越界调用的工具为准
    if has_direct_kw:
        return False, "文本为单点信息查询，判直答(忽略模型可能越界调用的规划工具)"

    # 3. 文本模糊：用强规划工具兜底
    if called_tools & _PLANNING_TOOLS:
        return True, f"文本模糊，但调用了强规划工具{sorted(called_tools & _PLANNING_TOOLS)}"
    return False, "文本无规划信号且未调强规划工具，判直答"



PLANNER_SYSTEM_PROMPT = (
    "你是旅游规划师，负责调用工具收集真实信息并产出初版行程。\n"
    "硬性要求：\n"
    "1. 价格、车次/航班时刻、开放时间、评分只能来自工具返回，禁止编造；"
    "工具没查到的不要写具体数字\n"
    "2. 完整多日规划必须查天气、景点、酒店；跨城往返必须查交通，"
    "去程返程都要有依据，不能只查去程就编返程\n"
    "3. 用户要求对比交通方式时，必须查到多种方式再对比，不能只给一种\n"
    "4. 信息齐全后停止调工具，不要重复查询相同内容\n"
    "5. 若被审核打回，按反馈针对性修改，保留没问题的部分\n"
    "6. 预算汇总由下游预算师用代码统一计算，你不负责算总账，"
    "只需给每个活动标注来自工具或明确估算的 cost\n"
    "7. 严禁假设用户没提供的信息：用户没说出发城市，就不要安排跨城大交通，"
    "把'需用户确认出发城市'写进 warnings，而不是自行选一个城市\n"
    "8. 被打回重做时只改被点名的问题，其余活动与费用原样保留；"
    "多日行程必须保留每晚住宿及其费用，严禁把住宿等已有费用项清零或删除"
    "9. 只有用户要完整多日行程时才查酒店/城际交通；用户只问美食推荐、天气、"
    "单个景点等单点信息时，只调对应工具并用自然语言回答，"
    "不要查酒店、不要扩展成多日行程\n"
)


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
    tool_map = get_tool_map()
    # 机制隔离：预算汇总是 Budgeter 职责，Planner 不绑定 calculate_budget
    planner_tools = [t for t in get_all_tools() if t.name != "calculate_budget"]
    bound = llm.bind_tools(planner_tools)
    cache = get_tool_cache()

    # 历史消息只用于本次推理，不重复回写；只回写本轮新建的消息
    context: list = [SystemMessage(content=PLANNER_SYSTEM_PROMPT)]
    memory_context = state.get("memory_context", "")
    if memory_context:
        context.append(SystemMessage(content=f"【用户画像与历史偏好】\n{memory_context}"))
    context.extend(state["messages"])

    new_messages: list = []
    feedback = state.get("reviewer_feedback", "")
    prev_draft = state.get("draft_itinerary")
    if feedback:
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

    async def run_one_tool(tc: dict) -> ToolMessage:
        """单个工具：缓存优先 → 重试 → 失败兜底，与单 Agent tool_node 同标准"""
        name, args, tc_id = tc["name"], tc["args"], tc["id"]
        cache_key = ToolCache.make_key(name, args)
        cached = cache.get(cache_key)
        if cached is not None:
            tool_trace.append({"name": name, "args": args, "status": "cache_hit"})
            return ToolMessage(content=cached, tool_call_id=tc_id)

        tool = tool_map.get(name)
        if tool is None:
            tool_trace.append({"name": name, "args": args, "status": "unknown_tool"})
            return ToolMessage(content=f"未知工具: {name}", tool_call_id=tc_id)

        last_error = None
        for attempt in range(MAX_TOOL_RETRIES + 1):
            try:
                result = await tool.ainvoke(args)
                result_str = result if isinstance(result, str) else str(result)
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
    direct_answer = ""
    for _ in range(MAX_PLANNER_ITERS):
        ai_msg: AIMessage = await bound.ainvoke(context)
        context.append(ai_msg)
        new_messages.append(ai_msg)

        if not ai_msg.tool_calls:
            stopped_naturally = True
            direct_answer = ai_msg.content if isinstance(ai_msg.content, str) else ""
            break
        tool_msgs = await asyncio.gather(*[run_one_tool(tc) for tc in ai_msg.tool_calls])
        context.extend(tool_msgs)
        new_messages.extend(tool_msgs)

    if not stopped_naturally:
        logger.warning("[Planner] 达到内部循环上限%d，强制进入结构化", MAX_PLANNER_ITERS)

    # ===== Supervisor 意图守卫：非规划请求走直答快路径，不强行结构化 =====
    called_tools = {t["name"] for t in tool_trace}
    user_text = " ".join(
        m.content for m in state["messages"] if getattr(m, "type", "") == "human"
    )
    is_planning, intent_reason = _detect_planning_intent(user_text, called_tools)
    logger.info("[Planner] 意图判定: is_planning=%s（%s）", is_planning, intent_reason)

    if not is_planning:
        logger.info("[Planner] 判定为非规划意图，走直答快路径，不生成行程")
        return {
            "messages": new_messages,
            "tool_trace": tool_trace,
            "is_planning": False,
            "draft_itinerary": None,
            "final_answer": direct_answer or "（无回答）",
            "reviewer_feedback": "",
            "review_status": "",
        }

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

    user_text = " ".join(
        m.content for m in state.get("messages", [])
        if getattr(m, "type", "") == "human"
    )


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
    }


def finalize_direct_node(state: dict) -> dict:
    """非规划请求的直答收尾：绕过 Budgeter/Reviewer，不付多角色成本"""
    logger.info("[finalize_direct] 非规划直答，跳过预算核算与审查")
    return {
        "final_itinerary": None,
        "itinerary": None,       # save_memory 见 itinerary 为 None 会自动跳过保存
        "forced_stop": False,
    }
