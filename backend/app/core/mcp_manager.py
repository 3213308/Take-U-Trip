# app/core/mcp_manager.py
"""MCP 工具连接管理器

职责：
1. 应用启动时连接 MCP Server（stdio 子进程），把 MCP 工具转成 LangChain BaseTool
2. 运行期通过 get_mcp_tools() 提供给 agent_node
3. 应用关闭时清理连接

为什么需要管理器：stdio MCP Server 是常驻子进程，连接有生命周期，
不能每次工具调用都重新拉起，也不能让连接在请求中途断开。
"""

import logging
import sys
from pathlib import Path

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

# backend/mcp_server/travel_server.py
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_SERVER_SCRIPT = _BACKEND_ROOT / "mcp_server" / "travel_server.py"

_client: MultiServerMCPClient | None = None
_mcp_tools: list[BaseTool] = []


async def init_mcp() -> list[BaseTool]:
    """应用/测试启动时调用：连接 Server 并加载工具"""
    global _client, _mcp_tools

    _client = MultiServerMCPClient({
        "travel": {
            "command": sys.executable,
            "args": [str(_SERVER_SCRIPT)],
            "transport": "stdio",
            "cwd": str(_BACKEND_ROOT),   # 保证子进程能 import app
        }
    })

    # get_tools 内部完成 initialize + tools/list，并转成 LangChain 工具
    _mcp_tools = await _client.get_tools()
    logger.info("MCP 工具已加载: %s", [t.name for t in _mcp_tools])
    return _mcp_tools


def get_mcp_tools() -> list[BaseTool]:
    """运行期获取已加载的 MCP 工具（未初始化时返回空列表）"""
    return _mcp_tools


async def close_mcp() -> None:
    """应用关闭时清理"""
    global _client, _mcp_tools
    _mcp_tools = []
    if _client is not None:
        # 生产环境应优雅关闭子进程；不同版本 API 有差异，这里做容错
        for method_name in ("aclose", "close"):
            method = getattr(_client, method_name, None)
            if method is not None:
                try:
                    result = method()
                    if hasattr(result, "__await__"):
                        await result
                except Exception as e:
                    logger.warning("关闭 MCP 连接异常: %s", e)
                break
    _client = None
