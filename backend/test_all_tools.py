"""测试全部 7 个工具"""

import asyncio
from app.tools import get_all_tools, get_tool_map


async def main():
    tools = get_all_tools()
    print(f"已注册 {len(tools)} 个工具：\n")
    for t in tools:
        print(f"  - {t.name}: {t.description[:50]}...")

    tool_map = get_tool_map()

    # 逐个测试
    test_cases = [
        ("get_weather", {"city": "成都", "start_date": "2025-10-01", "end_date": "2025-10-02"}),
        ("search_attractions", {"city": "成都", "category": "历史古迹"}),
        ("search_transport", {"departure": "北京", "destination": "成都", "date": "2025-10-01"}),
        ("search_hotels", {"city": "成都", "check_in": "2025-10-01", "check_out": "2025-10-03"}),
        ("search_restaurants", {"city": "成都", "cuisine": "火锅"}),
        ("calculate_route", {"from_location": "宽窄巷子", "to_location": "锦里古街"}),
        ("calculate_budget", {
            "items": [
                {"category": "交通", "amount": 1280, "description": "往返机票"},
                {"category": "住宿", "amount": 916, "description": "2晚酒店"},
                {"category": "餐饮", "amount": 500},
                {"category": "门票", "amount": 110},
            ],
            "total_budget": 2000,
        }),
    ]

    for name, args in test_cases:
        print(f"\n{'='*60}")
        print(f"工具: {name}")
        print(f"参数: {args}")
        print("-" * 60)
        result = await tool_map[name].ainvoke(args)
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
