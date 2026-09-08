# app/evaluation/compare_reports.py
"""单 Agent vs 多 Agent 基线对照

读取 baseline_report.json 与 multi_report.json，输出六维对照 Markdown：
总览质量/成本、病灶分布、分 case 稳定性与成本、多 Agent 协作健康度。
质量类指标看差值（越高越好），成本类指标看倍数（越低越好）。
"""

import json
from pathlib import Path

# 本文件位于 backend/app/evaluation/，两份 report 由 test 入口写在 backend/ 根目录
# parents[0]=evaluation → parents[1]=app → parents[2]=backend
BASE_DIR = Path(__file__).resolve().parents[2]
SINGLE_PATH = BASE_DIR / "baseline_report.json"
MULTI_PATH = BASE_DIR / "multi_report.json"
OUT_PATH = BASE_DIR / "comparison_report.md"



def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _diff(single: float, multi: float, higher_better: bool) -> str:
    """质量类：差值；返回 '单 → 多 (±差值)'。"""
    d = multi - single
    arrow = "↑" if d > 0 else ("↓" if d < 0 else "=")
    return f"{single:.2f} → {multi:.2f} ({arrow}{abs(d):.2f})"


def _ratio(single: float, multi: float) -> str:
    """成本类：倍数；返回 '单 → 多 (Nx)'。"""
    if single <= 0:
        return f"{single:.2f} → {multi:.2f} (—)"
    return f"{single:.2f} → {multi:.2f} ({multi/single:.2f}×)"


def build_comparison(single: dict, multi: dict) -> str:
    s, m = single["summary"], multi["summary"]
    sp, mp = single["per_case"], multi["per_case"]
    lines: list[str] = []

    lines.append("# 单 Agent vs 多 Agent 对照报告\n")
    sr, mr = s.get("runs_per_case"), m.get("runs_per_case")
    lines.append(f"- 单 Agent：{sr} 次/用例，共 {s['total_runs']} 次运行")
    lines.append(f"- 多 Agent：{mr} 次/用例，共 {m['total_runs']} 次运行")
    if sr != mr:
        lines.append(f"> ⚠️ 两边重复次数不一致（{sr} vs {mr}），质量对比仅供参考，"
                     f"请用相同 runs_per_case 重跑后再下结论。")
    lines.append("")

    # 一、总览
    lines.append("## 一、总览对照\n")
    lines.append("| 指标 | 单 Agent | 多 Agent | 变化 |")
    lines.append("|---|---|---|---|")
    lines.append(f"| 总通过率（越高越好） | {_diff(s['overall_pass_rate'], m['overall_pass_rate'], True)} |")
    lines.append(f"| Judge 均分（越高越好） | {_diff(s['avg_judge_score'], m['avg_judge_score'], True)} |")
    lines.append(f"| 平均延迟 s（越低越好） | {_ratio(s['avg_elapsed_sec'], m['avg_elapsed_sec'])} |")
    lines.append(f"| 平均 token（越低越好） | {_ratio(s['avg_total_tokens'], m['avg_total_tokens'])} |")
    lines.append(f"| 平均 LLM 调用次数（越低越好） | {_ratio(s['avg_llm_calls'], m['avg_llm_calls'])} |")
    lines.append("")

    # 二、病灶分布
    lines.append("## 二、病灶分布对照\n")
    lesions = sorted(set(s["lesion_distribution"]) | set(m["lesion_distribution"]))
    lines.append("| 病灶 | 单 Agent | 多 Agent |")
    lines.append("|---|---|---|")
    for key in lesions:
        lines.append(f"| {key} | {s['lesion_distribution'].get(key, '—')} "
                     f"| {m['lesion_distribution'].get(key, '—')} |")
    lines.append("")
    lines.append("> 注：「预算不一致」由 evaluate_budget_consistency 判定，"
                 "「分项合计远小于总预算（有结余）」也会被判失败，并非仅指超支，解读时需区分。\n")

    # 三、分 case
    lines.append("## 三、分 case 对照\n")
    lines.append("| 用例 | 单稳定性 | 多稳定性 | 单Judge | 多Judge | "
                 "单token | 多token | token倍数 | 单延迟s | 多延迟s |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for cid in sp:
        a, b = sp[cid], mp.get(cid, {})
        tok_ratio = (b.get("avg_tokens", 0) / a["avg_tokens"]
                     if a.get("avg_tokens") else 0)
        lines.append(
            f"| {cid} | {a['stability']} | {b.get('stability', '—')} "
            f"| {a['judge_score_avg']} | {b.get('judge_score_avg', '—')} "
            f"| {a['avg_tokens']:.0f} | {b.get('avg_tokens', 0):.0f} | {tok_ratio:.2f}× "
            f"| {a['avg_elapsed_sec']} | {b.get('avg_elapsed_sec', '—')} |"
        )
    lines.append("")

    # 四、多 Agent 协作健康度（单 Agent 无）
    lines.append("## 四、多 Agent 协作健康度（单 Agent 无此机制）\n")
    collab = m.get("collab", {})
    if collab:
        lines.append("| 指标 | 数值 |")
        lines.append("|---|---|")
        for k, v in collab.items():
            lines.append(f"| {k} | {v:.2f} |")
    else:
        lines.append("（多 Agent 报告中无 collab 字段）")
    lines.append("")

    # 五、可证伪目标对照
    lines.append("## 五、可证伪目标达成情况（多 Agent）\n")
    lines.append("- case_002 稳定性 ≥ 0.9："
                 f"实际 {mp.get('case_002_full_itinerary', {}).get('stability', '—')}")
    lines.append("- 预算不一致率 = 0：见上表病灶分布")
    lines.append("- case_003 Judge ≥ 8："
                 f"实际 {mp.get('case_003_intercity_transport', {}).get('judge_score_avg', '—')}")
    lines.append("- 总通过率 ≥ 0.95："
                 f"实际 {m['overall_pass_rate']}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    single = _load(SINGLE_PATH)
    multi = _load(MULTI_PATH)
    report = build_comparison(single, multi)
    OUT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n对照报告已保存: {OUT_PATH}")


if __name__ == "__main__":
    main()
