"""原生 MCP Client — 手写 MCP 协议交互，理解握手/发现/调用三步

这一步故意不用任何封装框架，直接用官方 SDK 的底层 ClientSession，
目的是让你看清楚 MCP 通信的完整生命周期。
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# server 脚本的绝对路径
SERVER_SCRIPT = Path(__file__).parent / "mcp_server" / "travel_server.py"


async def main():
    # 1. 配置并启动 MCP Server 子进程（用当前虚拟环境的 python）
    params = StdioServerParameters(
        command=sys.executable,          # 避免 Windows 路径问题
        args=[str(SERVER_SCRIPT)],
        cwd=str(Path(__file__).parent),  # 保证能 import app
    )

    # stdio_client 管理子进程生命周期，ClientSession 走协议
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # ===== 步骤1：initialize 握手 =====
            init_result = await session.initialize()
            print(f"[握手成功] Server: {init_result.serverInfo.name}")
            print(f"协议版本: {init_result.protocolVersion}\n")

            # ===== 步骤2：list_tools 工具发现 =====
            tools_resp = await session.list_tools()
            print(f"[工具发现] 共 {len(tools_resp.tools)} 个工具：")
            for tool in tools_resp.tools:
                print(f"\n  工具名: {tool.name}")
                print(f"  描述: {tool.description.strip().splitlines()[0]}")
                print(f"  输入Schema: {tool.inputSchema}")

            # ===== 步骤3：call_tool 调用工具 =====
            print("\n" + "=" * 60)
            print("[调用] mcp_get_weather")
            r1 = await session.call_tool(
                "mcp_get_weather", {"city": "成都", "date": "2025-10-01"}
            )
            print(r1.content[0].text)

            print("\n" + "=" * 60)
            print("[调用] mcp_search_attractions")
            r2 = await session.call_tool(
                "mcp_search_attractions", {"city": "成都", "category": "历史古迹"}
            )
            print(r2.content[0].text)

            # 错误处理演示：调用不存在的工具
            print("\n" + "=" * 60)
            print("[异常演示] 调用不存在的工具")
            r3 = await session.call_tool("not_exist", {})
            print(f"isError: {r3.isError}")
            if r3.isError:
                print(f"错误内容: {r3.content[0].text}")


if __name__ == "__main__":
    asyncio.run(main())
