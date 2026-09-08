"""测试 Agent 循环：并行调用 + 步数保护"""

import asyncio
import logging
from langchain_core.messages import HumanMessage

from app.core.agent_loop import AgentLoop

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main():
    agent = AgentLoop(max_iterations=8)

    # 测试1：并行调用（同时问天气和景点）
    print("\n" + "=" * 60)
    print("测试1：并行调用（同时问天气和景点）")
    print("=" * 60)
    messages = [HumanMessage(content="北京今天天气怎么样？有哪些必去景点？")]
    result = await agent.run(messages)

    print(f"\n循环轮数: {result['iterations']}")
    print(f"工具调用次数: {len(result['tool_trace'])}")
    for t in result['tool_trace']:
        print(f"  - {t['name']}({t['args']}) → {t['status']}")
    print(f"\n最终回答:\n{result['final_answer']}")

    # 测试2：不需要工具的问题（应该1轮结束）
    print("\n" + "=" * 60)
    print("测试2：不需要工具的问题")
    print("=" * 60)
    messages2 = [HumanMessage(content="你好，你能做什么？")]
    result2 = await agent.run(messages2)
    print(f"循环轮数: {result2['iterations']}（应该是1）")
    print(f"最终回答: {result2['final_answer'][:100]}...")


if __name__ == "__main__":
    asyncio.run(main())
