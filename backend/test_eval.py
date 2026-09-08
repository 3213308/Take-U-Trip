"""运行 Agent 评估集"""

import asyncio
import json
import logging

from app.evaluation.runner import run_evaluation, summarize

logging.basicConfig(level=logging.WARNING)  # 评估时减少噪音，只看结果


async def main():
    results = await run_evaluation()
    summary = summarize(results)

    print(f"\n\n{'#'*60}")
    print("# 评估报告")
    print(f"{'#'*60}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 详细结果存文件，方便分析失败案例
    with open("eval_report.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "details": results}, f, ensure_ascii=False, indent=2)
    print("\n详细报告已写入 eval_report.json")


if __name__ == "__main__":
    asyncio.run(main())
