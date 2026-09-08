"""测试四层记忆系统"""

import asyncio
import logging
from langchain_core.messages import HumanMessage

from app.core.graph import travel_graph
from app.core.state import TravelState
from app.memory.store import get_memory_store
from app.memory.cache import get_tool_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main():
    user_id = "test-user-001"

    # ===== 第一次对话 =====
    print("=" * 60)
    print("第一次对话：成都2日游")
    print("=" * 60)
    state1: TravelState = {
        "messages": [HumanMessage(content="帮我规划成都2日游，预算2000，喜欢历史古迹")],
        "iteration": 0, "tool_trace": [], "final_answer": "",
        "forced_stop": False, "itinerary": None,
        "user_id": user_id, "user_profile": {}, "memory_context": "", "tool_cache": {},
    }
    result1 = await travel_graph.ainvoke(state1, {"configurable": {"thread_id": "t1"}})

    store = get_memory_store()
    print(f"\n保存后用户画像: {store.get_profile(user_id)}")
    print(f"历史行程数: {len(store.get_recent_itineraries(user_id))}")

    # ===== 第二次对话（应该能看到记忆上下文）=====
    print("\n" + "=" * 60)
    print("第二次对话：应该记住用户偏好")
    print("=" * 60)
    state2: TravelState = {
        "messages": [HumanMessage(content="再帮我规划一个类似的行程")],
        "iteration": 0, "tool_trace": [], "final_answer": "",
        "forced_stop": False, "itinerary": None,
        "user_id": user_id, "user_profile": {}, "memory_context": "", "tool_cache": {},
    }
    result2 = await travel_graph.ainvoke(state2, {"configurable": {"thread_id": "t2"}})

    print(f"\n最终回答: {result2['final_answer']}")
    print(f"工具缓存大小: {get_tool_cache().size()}")


if __name__ == "__main__":
    asyncio.run(main())
