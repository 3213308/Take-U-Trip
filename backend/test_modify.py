# test_modify.py
"""两轮测试：先规划，再 modify，验证修改意见送入 planner 重做"""

import asyncio
import logging
import sys
import time

from langchain_core.messages import HumanMessage

from app.core.multi_graph import multi_agent_graph
from app.memory.cache import get_tool_cache
from app.memory.store import get_memory_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)


INITIAL = "帮我规划成都2日游，预算2000，喜欢历史古迹"
MODIFY = "第二天天气不好，露天活动去不了了，帮我调整一下第二天"


def build_state(user_text: str) -> dict:
    return {
        "messages": [HumanMessage(content=user_text)],
        "iteration": 0,
        "tool_trace": [],
        "final_answer": "",
        "forced_stop": False,
        "itinerary": None,
        "user_id": "modify-test",
        "user_profile": {},
        "memory_context": "",
        "tool_cache": {},
        "draft_itinerary": None,
        "is_planning": False,
        "budget_review": {},
        "review_status": "",
        "reviewer_feedback": "",
        "review_round": 0,
        "final_itinerary": None,
        "intent": "",
        "action": "",
        "slots": {},
        "missing_slots": [],
        "clarify_question": "",
    }


async def run_round(user_text: str, thread_id: str, round_num: int):
    config = {"configurable": {"thread_id": thread_id}}
    print("=" * 60)
    print(f"第{round_num}轮: {user_text}")
    print("=" * 60)

    t0 = time.perf_counter()
    async for chunk in multi_agent_graph.astream(
        build_state(user_text), config=config, stream_mode="updates"
    ):
        for node, update in chunk.items():
            if node == "__start__":
                continue
            if node == "intake":
                print(f"  [intake] intent={update.get('intent')} action={update.get('action')}")
            elif node == "planner":
                draft = update.get("draft_itinerary") or {}
                if draft:
                    print(f"  [planner] 产出行程: {draft.get('destination')} {draft.get('days')}天")
            elif node == "budgeter":
                br = update.get("budget_review", {})
                if br:
                    print(f"  [budgeter] 实际{br.get('actual_total')} / 预算{br.get('user_budget')}")
            elif node == "reviewer":
                print(f"  [reviewer] 第{update.get('review_round')}轮: {update.get('review_status')}")
            elif node == "answer":
                print(f"  [answer] 轻量回复")
            elif node == "finalize_multi":
                print(f"  [finalize] {update.get('final_answer')}")

    elapsed = time.perf_counter() - t0
    snapshot = await multi_agent_graph.aget_state(config)
    final = snapshot.values
    itin = final.get("final_itinerary")
    if itin:
        print(f"\n  行程: {itin.get('destination')} {itin.get('days')}天")
        for i, day in enumerate(itin.get("days_plan", []), 1):
            acts = [a.get("name") for a in day.get("activities", [])]
            print(f"  第{i}天: {acts}")
    else:
        print(f"\n  回答: {final.get('final_answer', '')[:200]}")
    print(f"  耗时 {elapsed:.1f}s\n")


async def main():
    get_memory_store().clear_all()
    get_tool_cache().clear()

    thread_id = "modify-test-001"

    # 第一轮：规划
    await run_round(INITIAL, thread_id, 1)

    # 第二轮：修改（同一个 thread_id，带着上一轮行程）
    await run_round(MODIFY, thread_id, 2)


if __name__ == "__main__":
    asyncio.run(main())
