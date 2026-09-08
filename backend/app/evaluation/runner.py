# app/evaluation/runner.py
"""评估运行器 — 跑全部用例，汇总指标"""

import asyncio
import logging
from dataclasses import asdict

from app.memory.store import get_memory_store
from app.memory.cache import get_tool_cache

from langchain_core.messages import HumanMessage

from app.core.graph import travel_graph
from app.core.state import TravelState
from app.evaluation.dataset import EVAL_CASES, EvalCase
from app.evaluation.judge import llm_judge
from app.evaluation.metrics import (
    evaluate_args,
    evaluate_budget_consistency,
    evaluate_efficiency,
    evaluate_schema,
    evaluate_tool_selection,
)

logger = logging.getLogger(__name__)


async def run_single_case(case: EvalCase) -> dict:
    state: TravelState = {
        "messages": [HumanMessage(content=case.input)],
        "iteration": 0, "tool_trace": [], "final_answer": "",
        "forced_stop": False, "itinerary": None,
        "user_id": case.user_id, "user_profile": {},
        "memory_context": "", "tool_cache": {},
    }
    config = {"configurable": {"thread_id": f"eval-{case.case_id}"}}

    result = await travel_graph.ainvoke(state, config=config)

    tool_trace = result.get("tool_trace", [])
    itinerary = result.get("itinerary")
    answer = result.get("final_answer", "")

    tool_evidence = "\n".join(
        getattr(m, "content", "")
        for m in result.get("messages", [])
        if getattr(m, "type", "") == "tool"
    )


    tool_metrics = evaluate_tool_selection(case, tool_trace)
    arg_metrics = evaluate_args(case, tool_trace)
    efficiency = evaluate_efficiency(case, result.get("iteration", 0), len(tool_trace))

    # 只有行程用例才检查结构和预算
    if case.expect_itinerary:
        schema_metrics = evaluate_schema(itinerary)
        budget_metrics = evaluate_budget_consistency(itinerary)
    else:
        # 信息查询/闲聊用例：itinerary 应为 None，answer 应非空
        schema_metrics = {"pass": itinerary is None and bool(answer),
                          "note": "非行程用例，要求直接文本回答"}
        budget_metrics = {"pass": True, "issues": []}

    judge_result = await llm_judge(
        case.input, case.check_points, itinerary, answer, tool_evidence
    )

    rule_pass = all([
        tool_metrics["pass"], arg_metrics["pass"],
        efficiency["pass"], schema_metrics["pass"],
    ])
    judge_checks = judge_result.get("check_results", [])
    judge_pass_rate = (
        sum(1 for c in judge_checks if c.get("passed")) / len(judge_checks)
        if judge_checks else 0
    )

    return {
        "case_id": case.case_id,
        "input": case.input,
        "expect_itinerary": case.expect_itinerary,
        "rule_pass": rule_pass,
        "tool_metrics": tool_metrics,
        "arg_metrics": arg_metrics,
        "efficiency": efficiency,
        "schema_metrics": schema_metrics,
        "budget_metrics": budget_metrics,
        "judge": judge_result,
        "judge_pass_rate": round(judge_pass_rate, 2),
        "overall_pass": rule_pass and judge_pass_rate >= 0.75,
    }


async def run_evaluation() -> list[dict]:
    """跑全部评估用例"""
    get_memory_store().clear_all()  # 新增：清空跨用例污染
    get_tool_cache().clear()

    results = []
    for case in EVAL_CASES:
        # 每个用例独立 user_id，双保险
        case.user_id = f"eval-{case.case_id}"
        logger.info("评估用例: %s", case.user_id)
        print(f"\n{'=' * 60}\n评估: {case.case_id}\n输入: {case.input}\n{'=' * 60}")
        r = await run_single_case(case)
        results.append(r)

        # 即时输出
        print(f"工具召回: {r['tool_metrics']['tool_recall']}  缺失: {r['tool_metrics']['missing_tools']}")
        print(f"参数正确: {r['arg_metrics']['pass']}  效率: {r['efficiency']['iterations']}轮")
        print(f"结构完整: {r['schema_metrics']['pass']}  预算一致: {r['budget_metrics']['pass']}")
        print(f"Judge分数: {r['judge'].get('score')}  通过率: {r['judge_pass_rate']}")
        print(f"综合: {'✅ PASS' if r['overall_pass'] else '❌ FAIL'}")
    return results


def summarize(results: list[dict]) -> dict:
    """汇总整体指标"""
    total = len(results)
    passed = sum(1 for r in results if r["overall_pass"])
    avg_iterations = sum(r["efficiency"]["iterations"] for r in results) / total
    avg_tool_calls = sum(r["efficiency"]["tool_calls"] for r in results) / total
    avg_recall = sum(r["tool_metrics"]["tool_recall"] for r in results) / total
    avg_judge = sum(r["judge"].get("score", 0) for r in results if r["judge"].get("score", -1) >= 0)
    judge_count = sum(1 for r in results if r["judge"].get("score", -1) >= 0)

    return {
        "total_cases": total,
        "passed": passed,
        "success_rate": round(passed / total, 2),
        "avg_iterations": round(avg_iterations, 2),
        "avg_tool_calls": round(avg_tool_calls, 2),
        "avg_tool_recall": round(avg_recall, 2),
        "avg_judge_score": round(avg_judge / judge_count, 2) if judge_count else 0,
        "failed_cases": [r["case_id"] for r in results if not r["overall_pass"]],
    }
