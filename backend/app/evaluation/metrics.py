# app/evaluation/metrics.py
"""规则评估器 — 不依赖 LLM 的确定性指标"""

from app.evaluation.dataset import EvalCase


def evaluate_tool_selection(case: EvalCase, tool_trace: list[dict]) -> dict:
    """工具选择：召回率（该调的调了没）+ 误调用（不该调的调了没）"""
    called = {t["name"] for t in tool_trace if t["status"] in ("ok", "cache_hit")}
    expected = set(case.expected_tools)
    forbidden = set(case.forbidden_tools)

    hit = expected & called
    missing = expected - called
    misused = forbidden & called

    recall = len(hit) / len(expected) if expected else 1.0  # 无期望工具时，不调用即满分
    precision = 1.0 if not misused else (len(called) - len(misused)) / len(called)

    return {
        "tool_recall": round(recall, 2),
        "tool_precision": round(precision, 2),
        "called_tools": sorted(called),
        "missing_tools": sorted(missing),
        "misused_tools": sorted(misused),
        "pass": len(missing) == 0 and len(misused) == 0,
    }


def evaluate_args(case: EvalCase, tool_trace: list[dict]) -> dict:
    """参数正确性：关键参数值是否符合期望"""
    actual_args: dict[str, dict] = {}
    for t in tool_trace:
        actual_args.setdefault(t["name"], t.get("args", {}))

    checks = []
    all_pass = True
    for tool_name, expected_params in case.expected_args.items():
        actual = actual_args.get(tool_name)
        if actual is None:
            checks.append({"tool": tool_name, "pass": False, "reason": "工具未被调用"})
            all_pass = False
            continue
        for key, expected_val in expected_params.items():
            actual_val = actual.get(key)
            ok = str(actual_val) == str(expected_val)
            if not ok:
                all_pass = False
            checks.append({
                "tool": tool_name, "param": key,
                "expected": expected_val, "actual": actual_val, "pass": ok,
            })

    return {"arg_checks": checks, "pass": all_pass}


def evaluate_efficiency(case: EvalCase, iterations: int, tool_call_count: int) -> dict:
    """执行效率：步数是否在合理范围"""
    return {
        "iterations": iterations,
        "tool_calls": tool_call_count,
        "max_allowed": case.max_iterations,
        "pass": iterations <= case.max_iterations,
    }


def evaluate_schema(itinerary: dict | None) -> dict:
    """结构完整性：结构化输出是否成功且关键字段齐全"""
    if not itinerary:
        return {"pass": False, "reason": "结构化输出失败", "missing": ["itinerary"]}

    required_top = ["destination", "days", "days_plan", "total_budget"]
    missing = [f for f in required_top if not itinerary.get(f)]

    # 校验每天的活动结构
    day_issues = []
    for i, day in enumerate(itinerary.get("days_plan", [])):
        if not day.get("activities"):
            day_issues.append(f"第{i+1}天无活动")
        for j, act in enumerate(day.get("activities", [])):
            for field_name in ["time", "name", "category"]:
                if not act.get(field_name):
                    day_issues.append(f"第{i+1}天活动{j+1}缺{field_name}")

    return {
        "pass": len(missing) == 0 and len(day_issues) == 0,
        "missing_fields": missing,
        "day_issues": day_issues,
    }


def evaluate_budget_consistency(itinerary: dict | None, tolerance: float = 1.0) -> dict:
    """预算一致性：活动费用累加 vs daily_budget，分项费用 vs total_budget

    容忍度 tolerance 元（模型可能四舍五入）
    """
    if not itinerary:
        return {"pass": False, "reason": "无行程"}

    issues = []

    # 每日活动费用 vs daily_budget
    for i, day in enumerate(itinerary.get("days_plan", [])):
        activity_sum = sum(a.get("cost", 0) for a in day.get("activities", []))
        daily = day.get("daily_budget", 0)
        # 注意：住宿可能在活动里也可能在分项里，这里只记录差异供分析
        if daily > 0 and abs(activity_sum - daily) > max(tolerance, daily * 0.3):
            issues.append(
                f"第{i+1}天活动费用合计{activity_sum:.0f}与daily_budget{daily:.0f}差异过大"
            )

    # 分项费用 vs total_budget
    # 注意语义：total_budget 是用户给的"预算上限"，parts_sum 是"实际花费"。
    # 两者本就不该相等——花得比预算少（有结余）是好事，不算失败；
    # 只有"明显超支"才是真问题。
    parts = ["transport_cost", "accommodation_cost", "food_cost", "attraction_cost"]
    parts_sum = sum(itinerary.get(p, 0) for p in parts)
    total = itinerary.get("total_budget", 0)
    over_budget_threshold = max(tolerance, total * 0.05)  # 超支容忍 5%，四舍五入误差
    if total > 0 and parts_sum > 0 and parts_sum > total + over_budget_threshold:
        issues.append(
            f"分项费用合计{parts_sum:.0f}超出用户预算{total:.0f}"
            f"（超支{parts_sum - total:.0f}）"
        )

    remaining = total - parts_sum
    return {
        "pass": len(issues) == 0,
        "issues": issues,
        "parts_sum": parts_sum,
        "total": total,
        "remaining": remaining,  # 新增：花完还剩多少，供报告展示，不影响 pass
    }


def evaluate_fact_grounding(itinerary: dict | None, tool_trace: list[dict],
                            tool_outputs: dict[str, list[str]]) -> dict:
    """事实溯源：行程中的景点门票价格是否来自工具返回

    tool_outputs: {工具名: [该工具每次返回的文本]]}
    思路：把所有工具返回拼成语料库，检查 itinerary 里的景点名+价格是否在语料中出现
    """
    if not itinerary:
        return {"pass": False, "ungrounded": [], "grounding_rate": 0.0}

    # 所有工具返回拼成"事实语料库"
    evidence = " ".join(text for texts in tool_outputs.values() for text in texts)

    ungrounded = []
    checked = 0
    grounded = 0

    for day in itinerary.get("days_plan", []):
        for act in day.get("activities", []):
            if act.get("category") != "景点" or act.get("cost", 0) == 0:
                continue
            checked += 1
            name = act.get("name", "")
            cost = str(int(act.get("cost", 0)))
            # 简化判定：景点名和价格都应能在工具语料中找到
            core_name = name.replace("参观", "").replace("游览", "").strip()
            if core_name[:3] in evidence and cost in evidence:
                grounded += 1
            else:
                ungrounded.append(f"{name} ¥{act['cost']}（工具返回中无依据）")

    rate = grounded / checked if checked else 1.0
    return {
        "pass": rate >= 0.8,
        "grounding_rate": round(rate, 2),
        "ungrounded": ungrounded,
    }
