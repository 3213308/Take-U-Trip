"""测试结构化输出 — 模型生成 Pydantic 格式的行程"""

import asyncio
import json
import logging
from langchain_core.messages import HumanMessage

from app.core.graph import travel_graph
from app.core.state import TravelState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main():
    initial_state: TravelState = {
        "messages": [HumanMessage(
            content="帮我规划成都2日游，预算2000元，喜欢历史古迹和美食，10月1日出发"
        )],
        "iteration": 0,
        "tool_trace": [],
        "final_answer": "",
        "forced_stop": False,
        "itinerary": None,
    }

    config = {"configurable": {"thread_id": "test-structured-001"}}

    print("正在生成结构化行程...")
    result = await travel_graph.ainvoke(initial_state, config=config)

    print(f"\n循环轮数: {result['iteration']}")
    print(f"工具调用: {len(result['tool_trace'])}")
    for t in result['tool_trace']:
        print(f"  - {t['name']}({t['args']}) → {t['status']}")

    itinerary = result.get("itinerary")
    if itinerary:
        print("\n" + "=" * 60)
        print("结构化行程（JSON）：")
        print("=" * 60)
        print(json.dumps(itinerary, ensure_ascii=False, indent=2))

        print("\n" + "=" * 60)
        print("行程摘要：")
        print("=" * 60)
        print(f"目的地: {itinerary['destination']}")
        print(f"天数: {itinerary['days']}")
        print(f"总预算: {itinerary['total_budget']}元")
        print(f"每日安排:")
        for i, day in enumerate(itinerary['days_plan'], 1):
            print(f"  第{i}天（{day['date']}）{day.get('theme', '')}: {len(day['activities'])}个活动")
            for act in day['activities']:
                print(f"    {act['time']} [{act['category']}] {act['name']} @ {act['location']} ¥{act['cost']}")
    else:
        print(f"\n结构化输出失败，纯文本回答: {result['final_answer']}")


if __name__ == "__main__":
    asyncio.run(main())
