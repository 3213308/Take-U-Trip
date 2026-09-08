"""测试 SSE 流式接口 — 观察 Agent 执行过程实时推送"""

import asyncio
import json

import httpx


async def main():
    url = "http://localhost:8000/api/chat/stream"
    payload = {
        "message": "成都2日游预算2000，喜欢历史古迹",
        "user_id": "sse-test",
    }

    event_name = None
    print("连接 SSE 接口...\n")

    # stream 模式：服务端每推一块就处理一块
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", url, json=payload) as resp:
            async for line in resp.aiter_lines():
                if not line:
                    continue

                # SSE 协议：event: xxx 行 + data: xxx 行
                if line.startswith("event: "):
                    event_name = line.removeprefix("event: ").strip()
                elif line.startswith("data: "):
                    data_str = line.removeprefix("data: ").strip()
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = data_str

                    # 按事件类型格式化输出
                    if event_name == "status":
                        print(f"[状态] {data.get('phase')}")
                    elif event_name == "tool_call":
                        print(f"[调用工具] {data['name']}({json.dumps(data['args'], ensure_ascii=False)})")
                    elif event_name == "tool_result":
                        print(f"[工具结果] {data['name']} → {data['status']}")
                    elif event_name == "final":
                        print(f"\n[最终结果] 轮数={data.get('iteration')}")
                        if data.get("itinerary"):
                            it = data["itinerary"]
                            print(f"  目的地: {it['destination']} {it['days']}天")
                            print(f"  总预算: {it['total_budget']}元")
                            for i, day in enumerate(it["days_plan"], 1):
                                print(f"  第{i}天 {day.get('theme', '')}: {len(day['activities'])}个活动")
                    elif event_name == "done":
                        print(f"\n[完成] thread_id={data.get('thread_id')}")
                    elif event_name == "error":
                        print(f"[错误] {data}")

                    event_name = None


if __name__ == "__main__":
    asyncio.run(main())
