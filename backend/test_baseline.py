"""单 Agent 基线测试入口 — 结果写入 baseline_report.json"""

import asyncio
import json
import logging
from pathlib import Path

from app.evaluation.baseline import run_baseline

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main():
    print("开始单 Agent 基线测试（5用例 × 3次 = 15次运行，约需几分钟）...")
    report = await run_baseline(runs_per_case=3)

    out = Path(__file__).parent / "baseline_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    s = report["summary"]
    print("\n" + "=" * 60)
    print("单 Agent 基线汇总")
    print("=" * 60)
    print(f"总运行次数: {s['total_runs']}")
    print(f"总通过率: {s['overall_pass_rate']}")
    print(f"Judge 均分: {s['avg_judge_score']}")
    print(f"平均延迟: {s['avg_elapsed_sec']}s/次")
    print(f"平均 token: {s['avg_total_tokens']}/次")
    print(f"平均 LLM 调用: {s['avg_llm_calls']}次")
    print("\n病灶分布（多Agent角色要对着这些设计）:")
    for lesion, rate in s["lesion_distribution"].items():
        print(f"  {lesion}: {rate}")

    print("\n各用例稳定性:")
    for cid, pc in report["per_case"].items():
        print(f"  {cid}: 稳定性{pc['stability']} Judge{pc['judge_score_avg']}"
              f" 波动±{pc['judge_score_stdev']}")

    print(f"\n报告已保存: {out}")


if __name__ == "__main__":
    asyncio.run(main())
