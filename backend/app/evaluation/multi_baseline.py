# app/evaluation/multi_baseline.py
"""多 Agent 基线测试 —— 与单 Agent baseline 同口径对照

复用同一套数据集、规则指标、LLM Judge、UsageTracker 成本口径与聚合逻辑，
只把"被测图"换成 multi_agent_graph、state 换成 MultiAgentState，
从而保证单/多对比只有架构这一个变量。

额外记录多 Agent 协作健康度：分流正确率、打回率、强制放行率、平均审查轮数。
"""

import logging
import time

from langchain_core.messages import HumanMessage

from app.core.multi_graph import multi_agent_graph
from app.core.multi_state import MultiAgentState
from app.evaluation.baseline import _avg, aggregate_all, aggregate_case
from app.evaluation.dataset import EVAL_CASES, EvalCase
from app.evaluation.judge import llm_judge
from app.evaluation.metrics import (
    evaluate_args,
    evaluate_budget_consistency,
    evaluate_efficiency,
    evaluate_schema,
    evaluate_tool_selection,
)
from app.evaluation.usage_tracker import UsageTracker
from app.memory.cache import get_tool_cache
from app.memory.store import get_memory_store

logger = logging.getLogger(__name__)


def _build_multi_state(case: EvalCase) -> MultiAgentState:
    """构造多 Agent 图的初始 state，字段与 MultiAgentState 对齐。"""
    return {
        "messages": [HumanMessage(content=case.input)],
        "iteration": 0,
        "tool_trace": [],
        "final_answer": "",
        "forced_stop": False,
        "itinerary": None,
        "user_id": case.user_id,
        "user_profile": {},
        "memory_context": "",
        "tool_cache": {},
        # 三角色协作字段
        "draft_itinerary": None,
        "budget_review": {},
        "review_status": "",
        "reviewer_feedback": "",
        "review_round": 0,
        "final_itinerary": None,
        "is_planning": False,
    }


async def run_once_multi(case: EvalCase, run_idx: int) -> dict:
    """单个用例跑一次多 Agent 图，返回质量 + 成本 + 协作健康度。"""
    tracker = UsageTracker()
    config = {
        "configurable": {"thread_id": f"multi-{case.case_id}-{run_idx}"},
        "callbacks": [tracker],   # 与单 Agent 同一个采集器，成本口径一致
    }

    t0 = time.perf_counter()
    result = await multi_agent_graph.ainvoke(_build_multi_state(case), config=config)
    elapsed = time.perf_counter() - t0

    tool_trace = result.get("tool_trace", [])
    itinerary = result.get("final_itinerary") or result.get("itinerary")
    answer = result.get("final_answer", "")
    is_planning = bool(result.get("is_planning"))
    review_round = result.get("review_round", 0)
    forced_stop = bool(result.get("forced_stop"))

    tool_evidence = "\n".join(
        getattr(m, "content", "")
        for m in result.get("messages", [])
        if getattr(m, "type", "") == "tool"
    )

    # 规则指标（与 baseline 完全一致，保证可比）
    tool_metrics = evaluate_tool_selection(case, tool_trace)
    arg_metrics = evaluate_args(case, tool_trace)
    # 多 Agent 无单一 ReAct iteration，用"审查轮数+1"作为宏观角色轮次
    macro_iters = review_round + 1
    efficiency = evaluate_efficiency(case, macro_iters, len(tool_trace))
    if case.expect_itinerary:
        schema_metrics = evaluate_schema(itinerary)
        budget_metrics = evaluate_budget_consistency(itinerary)
    else:
        # 非规划用例应走直答、不产出行程；同时校验 Supervisor 分流是否正确
        schema_metrics = {"pass": itinerary is None and bool(answer)}
        budget_metrics = {"pass": True, "issues": []}

    judge_result = await llm_judge(
        case.input, case.check_points, itinerary, answer, tool_evidence
    )
    judge_checks = judge_result.get("check_results", [])
    judge_pass_rate = (
        sum(1 for c in judge_checks if c.get("passed")) / len(judge_checks)
        if judge_checks else 0
    )

    rule_pass = all([
        tool_metrics["pass"], arg_metrics["pass"],
        efficiency["pass"], schema_metrics["pass"],
    ])
    overall_pass = rule_pass and judge_pass_rate >= 0.75

    usage = tracker.snapshot()
    return {
        "run_idx": run_idx,
        "rule_pass": rule_pass,
        "overall_pass": overall_pass,
        "tool_metrics": tool_metrics,
        "schema_metrics": schema_metrics,
        "budget_metrics": budget_metrics,
        "judge_score": judge_result.get("score", -1),
        "judge_pass_rate": round(judge_pass_rate, 2),
        "judge_weaknesses": judge_result.get("weaknesses", []),
        # —— 多 Agent 协作健康度（单 Agent 无对应字段）——
        "is_planning": is_planning,
        "route_correct": is_planning == case.expect_itinerary,
        "review_round": review_round,
        "was_revised": review_round >= 1,
        "forced_stop": forced_stop,
        "runtime": {
            "elapsed_sec": round(elapsed, 2),
            "llm_calls": usage["llm_calls"],
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_tokens": usage["total_tokens"],
            "agent_iterations": macro_iters,
            "tool_calls": len(tool_trace),
        },
    }


async def run_multi_baseline(runs_per_case: int = 3) -> dict:
    """跑完整多 Agent 基线：每用例重复 runs_per_case 次，用例间清空记忆隔离。"""
    get_memory_store().clear_all()
    get_tool_cache().clear()

    all_runs: list[dict] = []
    per_case: dict[str, dict] = {}

    for case in EVAL_CASES:
        case.user_id = f"multi-{case.case_id}"
        print(f"\n{'='*60}\n多Agent用例: {case.case_id}（重复{runs_per_case}次）\n{'='*60}")

        case_runs = []
        for i in range(runs_per_case):
            r = await run_once_multi(case, i)
            case_runs.append(r)
            all_runs.append(r)
            rt = r["runtime"]
            print(f"  第{i+1}次: {'PASS' if r['overall_pass'] else 'FAIL'} | "
                  f"Judge {r['judge_score']} | 分流{'对' if r['route_correct'] else '错'} | "
                  f"审查{r['review_round']}轮{'[强制放行]' if r['forced_stop'] else ''} | "
                  f"{rt['elapsed_sec']}s | {rt['total_tokens']} tok")

        per_case[case.case_id] = aggregate_case(case_runs)
        pc = per_case[case.case_id]
        print(f"  → 稳定性 {pc['stability']}，Judge均分 {pc['judge_score_avg']}"
              f"（{pc['judge_score_range'][0]}~{pc['judge_score_range'][1]}）")

    summary = aggregate_all(all_runs, per_case)

    # 追加多 Agent 专属的协作健康度汇总
    summary["collab"] = {
        "分流正确率": _avg([1 if r["route_correct"] else 0 for r in all_runs]),
        "打回率(至少重做1次)": _avg([1 if r["was_revised"] else 0 for r in all_runs]),
        "强制放行率": _avg([1 if r["forced_stop"] else 0 for r in all_runs]),
        "平均审查轮数": _avg([r["review_round"] for r in all_runs]),
    }
    return {"summary": summary, "per_case": per_case, "all_runs": all_runs}
