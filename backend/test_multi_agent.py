# test_multi_agent.py
"""多智能体端到端冒烟：逐节点观察 Planner→Budgeter→Reviewer 的协作与打回

用 stream_mode="updates" 流式拿每个节点的增量输出，
比 ainvoke 最后一次性给结果更适合看清多角色协作过程。
"""

import asyncio
import logging
import sys
import time

from langchain_core.messages import HumanMessage

from app.core.multi_graph import multi_agent_graph
from app.core.multi_state import MultiAgentState
from app.memory.cache import get_tool_cache
from app.memory.store import get_memory_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)   # 压掉 HTTP 噪音，保留 app 日志

# 用法：python test_multi_agent.py [plan|direct|food|intercity]
#   plan       多日规划 → 走 Planner→Budgeter→Reviewer 精修
#   direct     闲聊/能力询问 → 走直答快路径（本次要验证的第二条路）
#   food       美食推荐（非行程）→ 也应走直答
#   intercity  跨城规划 → 易触发打回
PRESETS = {
    "plan": "帮我规划成都2日游，预算2000，喜欢历史古迹",
    "direct": "你好，你能做什么？",
    "food": "去成都玩，主要想吃火锅和小吃，推荐一下",
    "intercity": "我从北京去成都玩3天，怎么去比较好，预算3000",
}
_mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
USER_TEXT = PRESETS.get(_mode, _mode)   # 传预设名走预设，传其他字符串就当原始问题


def build_state(user_text: str, user_id: str = "multi-smoke") -> MultiAgentState:
    return {
        "messages": [HumanMessage(content=user_text)],
        "iteration": 0,
        "tool_trace": [],
        "final_answer": "",
        "forced_stop": False,
        "itinerary": None,
        "user_id": user_id,
        "user_profile": {},
        "memory_context": "",
        "tool_cache": {},
        # 多智能体协作字段
        "draft_itinerary": None,
        "is_planning": False,
        "budget_review": {},
        "review_status": "",
        "reviewer_feedback": "",
        "review_round": 0,
        "final_itinerary": None,
    }


def print_node_update(node: str, update: dict) -> None:
    """打印单个节点的关键增量"""
    print(f"\n── 节点 [{node}] ──")

    if node == "planner":
        if update.get("is_planning") is False:
            print("  Planner 判定为非规划意图 → 走直答快路径（不生成行程）")
        else:
            draft = update.get("draft_itinerary") or {}
            print(f"  Planner 产出初版: {draft.get('destination')} {draft.get('days')}天")

    elif node == "budgeter":
        br = update.get("budget_review", {}) or {}
        if br and not br.get("error"):
            balance = (f"超支{br['over_amount']}" if br.get("is_over_budget")
                       else f"剩余{br['remaining']}")
            print(f"  Budgeter 确定性重算: 实际花费 {br['actual_total']} / "
                  f"用户预算 {br['user_budget']}（{balance}）")
            print(f"  四大分项: {br['parts']}")

    elif node == "reviewer":
        print(f"  Reviewer 第 {update.get('review_round')} 轮裁决: "
              f"{update.get('review_status')}")
        feedback = update.get("reviewer_feedback", "")
        if feedback:
            print(f"  ↓ 打回意见（将送回 Planner）:\n    {feedback}")

    elif node == "finalize_multi":
        print(f"  定稿，forced_stop={update.get('forced_stop')}，"
              f"answer={update.get('final_answer')}")

    elif node == "finalize_direct":
        print("  直答收尾：跳过 Budgeter/Reviewer，不付多角色成本")

    elif node in ("load_memory", "save_memory"):
        print("  （记忆节点）")


async def main() -> None:
    get_memory_store().clear_all()
    get_tool_cache().clear()

    config = {"configurable": {"thread_id": "multi-smoke-001"}}
    print("=" * 72)
    print(f"用户需求: {USER_TEXT}")
    print("=" * 72)

    t0 = time.perf_counter()
    planner_count = 0
    async for chunk in multi_agent_graph.astream(
        build_state(USER_TEXT), config=config, stream_mode="updates"
    ):
        for node, update in chunk.items():
            if node == "__start__":
                continue
            if node == "planner":
                planner_count += 1
                print(f"\n{'★' if planner_count > 1 else ''} Planner 第 {planner_count} 次执行")
            print_node_update(node, update)
    elapsed = time.perf_counter() - t0

    # 过程用 updates 观察，最终结果用 checkpointer 里的权威完整 state
    snapshot = await multi_agent_graph.aget_state(config)
    final = snapshot.values

    print("\n" + "=" * 72)
    print("最终定稿")
    print("=" * 72)
    itin = final.get("final_itinerary")

    if itin:
        # ===== 规划路径：展示结构化行程 =====
        print(f"目的地: {itin.get('destination')} | 天数: {itin.get('days')} | "
              f"审查轮数: {final.get('review_round')} | Planner执行: {planner_count}次")

        print("\n每日安排（注意 daily_budget 是 Budgeter 重算的，不是 LLM 填的）:")
        for i, day in enumerate(itin.get("days_plan", []), 1):
            print(f"  第{i}天 {day.get('theme')}: "
                  f"{len(day.get('activities', []))}个活动, daily_budget={day.get('daily_budget')}")

        print("\n最终 warnings:")
        for w in itin.get("warnings", []):
            print(f"  - {w}")
    else:
        # ===== 直答路径：展示自然语言回答，确认没有被强行做成行程 =====
        print("【直答快路径 · 未生成行程】")
        print("最终回答：")
        print(final.get("final_answer", "（空回答）"))

    print(f"\n工具轨迹共 {len(final.get('tool_trace', []))} 条 | 端到端耗时 {elapsed:.2f}s")
    if not itin:
        print(">>> 本次走直答快路径：planner → finalize_direct → save_memory，未经过 Budgeter/Reviewer")
    elif planner_count > 1:
        print(">>> 本次发生了打回重做，这就是单 Agent 没有的自我纠错闭环")
    else:
        print(">>> 本次初版即通过，未触发打回（正常，说明初版质量已达标）")


if __name__ == "__main__":
    asyncio.run(main())
