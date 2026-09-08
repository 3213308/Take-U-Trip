"""对比测试：Prompt 版 ReAct vs 原生 FC 版 ReAct"""

import asyncio
import logging
import time
from langchain_core.messages import HumanMessage

from app.core.agent_loop import AgentLoop        # FC 版
from app.core.react_prompt import PromptReActLoop  # Prompt 版

logging.basicConfig(level=logging.WARNING)  # 减少日志，方便看对比


async def main():
    question = "成都今天天气怎么样？有哪些必去景点？"

    print("=" * 70)
    print(f"问题: {question}")
    print("=" * 70)

    # ===== Prompt 版 =====
    print("\n【Prompt 版 ReAct】")
    print("-" * 40)
    prompt_agent = PromptReActLoop(max_iterations=8)
    t0 = time.time()
    result_prompt = await prompt_agent.run(question)
    t1 = time.time()

    print(f"轮数: {result_prompt['iterations']}")
    print(f"工具调用: {len(result_prompt['tool_trace'])}")
    for t in result_prompt['tool_trace']:
        print(f"  - {t['name']}({t['args']}) → {t['status']}")
    print(f"耗时: {t1-t0:.2f}s")
    print(f"回答预览: {result_prompt['final_answer'][:150]}...")

    # ===== FC 版 =====
    print("\n【原生 FC 版 ReAct】")
    print("-" * 40)
    fc_agent = AgentLoop(max_iterations=8)
    t2 = time.time()
    result_fc = await fc_agent.run([HumanMessage(content=question)])
    t3 = time.time()

    print(f"轮数: {result_fc['iterations']}")
    print(f"工具调用: {len(result_fc['tool_trace'])}")
    for t in result_fc['tool_trace']:
        print(f"  - {t['name']}({t['args']}) → {t['status']}")
    print(f"耗时: {t3-t2:.2f}s")
    print(f"回答预览: {result_fc['final_answer'][:150]}...")

    # ===== 对比总结 =====
    print("\n" + "=" * 70)
    print("对比总结")
    print("=" * 70)
    print(f"{'维度':<15} {'Prompt 版':<20} {'FC 版':<20}")
    print("-" * 55)
    print(f"{'协议':<15} {'纯文本 Thought/Action':<20} {'结构化 tool_calls':<20}")
    print(f"{'解析':<15} {'正则解析（易出错）':<20} {'API 层自动解析':<20}")
    print(f"{'并行调用':<15} {'不支持（一次一个）':<20} {'支持（一次多个）':<20}")
    print(f"{'稳定性':<15} {'依赖模型遵守格式':<20} {'协议强制，更稳定':<20}")
    print(f"{'轮数':<15} {result_prompt['iterations']:<20} {result_fc['iterations']:<20}")
    print(f"{'耗时':<15} {t1-t0:.2f}s{'<18}':<14} {t3-t2:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
