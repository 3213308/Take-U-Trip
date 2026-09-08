# app/evaluation/baseline.py
"""单 Agent 基线测试 — 多智能体改造前的对照基准

四类指标：
1. 质量：规则指标 + Judge（复用评估框架）
2. 成本：token、LLM 调用次数、端到端延迟（多Agent要对比的核心代价）
3. 稳定性：同一用例重复 N 次，量化 LLM 随机性
4. 病灶分布：统计各类错误出现频次，为多Agent角色设计提供数据依据

注意：token 只统计 Agent 图本身，不含 Judge（评估成本两边相同，对比时公平）
"""

import logging
import statistics
import time

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
from app.memory.cache import get_tool_cache
from app.memory.store import get_memory_store

from app.evaluation.usage_tracker import UsageTracker

logger = logging.getLogger(__name__)


def collect_runtime(result: dict, elapsed: float, tracker: UsageTracker) -> dict:
    """运行时成本：LLM 次数/token 以 UsageTracker 回调为准（统一公平口径），
    迭代步数与工具次数仍从最终 state 提取。"""
    usage = tracker.snapshot()
    return {
        "elapsed_sec": round(elapsed, 2),
        "llm_calls": usage["llm_calls"],
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": usage["total_tokens"],
        "agent_iterations": result.get("iteration", 0),
        "tool_calls": len(result.get("tool_trace", [])),
    }



async def run_once(case: EvalCase, run_idx: int) -> dict:
    """单个用例跑一次，返回质量+成本完整指标"""
    state: TravelState = {
        "messages": [HumanMessage(content=case.input)],
        "iteration": 0, "tool_trace": [], "final_answer": "",
        "forced_stop": False, "itinerary": None,
        "user_id": case.user_id, "user_profile": {},
        "memory_context": "", "tool_cache": {},
    }
    tracker = UsageTracker()
    config = {
        "configurable": {"thread_id": f"baseline-{case.case_id}-{run_idx}"},
        "callbacks": [tracker],
    }

    t0 = time.perf_counter()
    result = await travel_graph.ainvoke(state, config=config)
    elapsed = time.perf_counter() - t0

    tool_trace = result.get("tool_trace", [])
    itinerary = result.get("itinerary")
    answer = result.get("final_answer", "")

    tool_evidence = "\n".join(
        getattr(m, "content", "")
        for m in result.get("messages", [])
        if getattr(m, "type", "") == "tool"
    )

    # 规则指标（与 runner 完全一致，保证可比）
    tool_metrics = evaluate_tool_selection(case, tool_trace)
    arg_metrics = evaluate_args(case, tool_trace)
    efficiency = evaluate_efficiency(case, result.get("iteration", 0), len(tool_trace))
    if case.expect_itinerary:
        schema_metrics = evaluate_schema(itinerary)
        budget_metrics = evaluate_budget_consistency(itinerary)
    else:
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
        "runtime": collect_runtime(result, elapsed, tracker),
    }


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0


def aggregate_case(runs: list[dict]) -> dict:
    """聚合单个用例的 N 次运行：稳定性 + 均值 + 波动"""
    scores = [r["judge_score"] for r in runs]
    passes = [r["overall_pass"] for r in runs]
    tokens = [r["runtime"]["total_tokens"] for r in runs]
    elapsed = [r["runtime"]["elapsed_sec"] for r in runs]
    llm_calls = [r["runtime"]["llm_calls"] for r in runs]

    return {
        "runs": len(runs),
        "pass_count": sum(passes),
        "stability": round(sum(passes) / len(passes), 2),   # 稳定性=通过率
        "judge_score_avg": _avg(scores),
        "judge_score_range": [min(scores), max(scores)],    # 分数极差看波动
        "judge_score_stdev": round(statistics.pstdev(scores), 2) if len(scores) > 1 else 0,
        "avg_tokens": _avg(tokens),
        "avg_elapsed_sec": _avg(elapsed),
        "avg_llm_calls": _avg(llm_calls),
    }


def aggregate_all(all_runs: list[dict], per_case: dict) -> dict:
    """全局汇总 + 病灶分布统计"""
    n = len(all_runs)

    # 病灶：每类错误在多少次运行中出现
    lesions = {
        "工具漏调(missing_tools非空)": 0,
        "预算不一致(budget_metrics失败)": 0,
        "schema/意图失败": 0,
        "Judge检查点未全过(<1.0)": 0,
    }
    for r in all_runs:
        if r["tool_metrics"].get("missing_tools"):
            lesions["工具漏调(missing_tools非空)"] += 1
        if not r["budget_metrics"].get("pass"):
            lesions["预算不一致(budget_metrics失败)"] += 1
        if not r["schema_metrics"].get("pass"):
            lesions["schema/意图失败"] += 1
        if r["judge_pass_rate"] < 1.0:
            lesions["Judge检查点未全过(<1.0)"] += 1

    # 转成占比
    lesion_rate = {k: f"{v}/{n} = {round(v/n, 2)}" for k, v in lesions.items()}

    return {
        "runs_per_case": n // len(EVAL_CASES),
        "total_runs": n,
        "overall_pass_rate": _avg([1 if r["overall_pass"] else 0 for r in all_runs]),
        "avg_judge_score": _avg([r["judge_score"] for r in all_runs]),
        "avg_elapsed_sec": _avg([r["runtime"]["elapsed_sec"] for r in all_runs]),
        "avg_total_tokens": _avg([r["runtime"]["total_tokens"] for r in all_runs]),
        "avg_llm_calls": _avg([r["runtime"]["llm_calls"] for r in all_runs]),
        "lesion_distribution": lesion_rate,
    }


async def run_baseline(runs_per_case: int = 3) -> dict:
    """跑完整基线：每个用例重复 runs_per_case 次"""
    get_memory_store().clear_all()
    get_tool_cache().clear()

    all_runs: list[dict] = []
    per_case: dict[str, dict] = {}

    for case in EVAL_CASES:
        case.user_id = f"baseline-{case.case_id}"
        print(f"\n{'='*60}\n基线用例: {case.case_id}（重复{runs_per_case}次）\n{'='*60}")

        case_runs = []
        for i in range(runs_per_case):
            r = await run_once(case, i)
            case_runs.append(r)
            all_runs.append(r)
            rt = r["runtime"]
            print(f"  第{i+1}次: {'PASS' if r['overall_pass'] else 'FAIL'} | "
                  f"Judge {r['judge_score']} | {rt['elapsed_sec']}s | "
                  f"{rt['total_tokens']} tokens | {rt['llm_calls']}次LLM调用")

        per_case[case.case_id] = aggregate_case(case_runs)
        pc = per_case[case.case_id]
        print(f"  → 稳定性 {pc['stability']}，Judge均分 {pc['judge_score_avg']}"
              f"（{pc['judge_score_range'][0]}~{pc['judge_score_range'][1]}）")

    summary = aggregate_all(all_runs, per_case)
    return {"summary": summary, "per_case": per_case, "all_runs": all_runs}
