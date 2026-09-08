# test_langgraph.py
"""测试 LangGraph 版 ReAct 循环"""

import asyncio
import logging
from langchain_core.messages import HumanMessage

from app.core.graph import travel_graph
from app.core.state import TravelState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main():
    initial_state: TravelState = {
        "messages": [HumanMessage(content="成都今天天气怎么样？有哪些必去景点？")],
        "iteration": 0,
        "tool_trace": [],
        "final_answer": "",
        "forced_stop": False,
    }

    config = {"configurable": {"thread_id": "test-thread-001"}}

    print("正在执行 LangGraph ReAct 循环...")
    result = await travel_graph.ainvoke(initial_state, config=config)

    print("\n" + "=" * 60)
    print(f"循环轮数: {result['iteration']}")
    print(f"工具调用: {len(result['tool_trace'])}")
    for t in result['tool_trace']:
        print(f"  - {t['name']}({t['args']}) → {t['status']}")
    print(f"是否强制终止: {result['forced_stop']}")
    print(f"\n最终回答:\n{result['final_answer']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
