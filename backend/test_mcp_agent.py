"""测试 Agent 同时使用本地工具和 MCP 工具"""

import asyncio
import logging

from langchain_core.messages import HumanMessage

from app.core.graph import travel_graph
from app.core.mcp_manager import close_mcp, get_mcp_tools, init_mcp
from app.core.state import TravelState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main():
    # 1. 启动时连接 MCP Server
    await init_mcp()
    mcp_names = [t.name for t in get_mcp_tools()]
    print(f"已加载 MCP 工具: {mcp_names}\n")

    # 2. 跑 Agent（故意只问天气和景点，这两类本地和 MCP 都有）
    state: TravelState = {
        "messages": [HumanMessage(content="成都天气怎么样？有哪些历史古迹？")],
        "iteration": 0, "tool_trace": [], "final_answer": "",
        "forced_stop": False, "itinerary": None,
        "user_id": "mcp-test", "user_profile": {},
        "memory_context": "", "tool_cache": {},
    }
    result = await travel_graph.ainvoke(
        state, config={"configurable": {"thread_id": "mcp-agent-001"}}
    )

    # 3. 分析工具来源
    print("\n" + "=" * 60)
    print("工具调用轨迹：")
    local_count, mcp_count = 0, 0
    for t in result["tool_trace"]:
        source = "MCP远程" if t["name"].startswith("mcp_") else "本地"
        if t["name"].startswith("mcp_"):
            mcp_count += 1
        else:
            local_count += 1
        print(f"  [{source}] {t['name']}({t['args']}) → {t['status']}")

    print(f"\n本地工具调用 {local_count} 次，MCP 工具调用 {mcp_count} 次")
    print(f"循环轮数: {result['iteration']}")
    print(f"\n最终回答:\n{result['final_answer'][:500]}")

    await close_mcp()


if __name__ == "__main__":
    asyncio.run(main())
