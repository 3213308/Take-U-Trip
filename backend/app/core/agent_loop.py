# app/core/agent_loop.py
"""Agent 循环引擎 — 生产级 ReAct 循环

核心能力：
1. 并行工具调用（asyncio.gather）
2. 工具失败自动重试（最多2次）
3. 最大步数保护（max_iterations）
4. 完整的工具调用追踪（tool_trace）
5. 优雅的错误处理（工具失败不崩溃，返回错误信息给模型）

"""

import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool

from app.config import get_settings
from app.llm.client import get_llm
from app.tools import get_all_tools, get_tool_map

logger = logging.getLogger(__name__)
settings = get_settings()

# 工具最大重试次数
MAX_TOOL_RETRIES = 2


class AgentLoop:
    """ReAct 循环引擎"""

    def __init__(self, max_iterations: int | None = None):
        self.llm = get_llm()
        self.tools: list[BaseTool] = get_all_tools()
        self.tool_map: dict[str, BaseTool] = get_tool_map()
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.max_iterations = max_iterations or settings.MAX_ITERATIONS
        self.tool_trace: list[dict[str, Any]] = []

    async def run(self, messages: list[BaseMessage]) -> dict[str, Any]:
        """执行 Agent 循环，返回最终结果

        Returns:
            {
                "messages": 完整消息列表,
                "final_answer": 最终文本回答,
                "tool_trace": 工具调用记录,
                "iterations": 实际循环轮数,
            }
        """
        self.tool_trace = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.info("=== Agent 循环第 %d/%d 轮 ===", iteration, self.max_iterations)

            # ===== 1. LLM 推理 =====
            response: AIMessage = await self.llm_with_tools.ainvoke(messages)
            messages.append(response)

            tool_calls = response.tool_calls

            # ===== 2. 没有工具调用 → 循环结束 =====
            if not tool_calls:
                logger.info("模型未调用工具，循环结束")
                return {
                    "messages": messages,
                    "final_answer": response.content,
                    "tool_trace": self.tool_trace,
                    "iterations": iteration,
                }

            logger.info("模型发起 %d 个工具调用", len(tool_calls))

            # ===== 3. 并行执行所有工具 =====
            tool_messages = await self._execute_tools_parallel(tool_calls)
            messages.extend(tool_messages)

        # ===== 4. 达到最大步数，强制结束 =====
        logger.warning("达到最大迭代次数 %d，强制结束", self.max_iterations)
        return {
            "messages": messages,
            "final_answer": "（达到最大思考步数，已强制结束）",
            "tool_trace": self.tool_trace,
            "iterations": iteration,
            "forced_stop": True,
        }

    async def _execute_tools_parallel(self, tool_calls: list[dict]) -> list[ToolMessage]:
        """并行执行多个工具调用，含重试机制"""

        async def execute_single(tc: dict) -> ToolMessage:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_id = tc["id"]

            tool = self.tool_map.get(tool_name)
            if tool is None:
                error_msg = f"未知工具: {tool_name}"
                logger.error(error_msg)
                self.tool_trace.append({"name": tool_name, "args": tool_args, "status": "error", "error": error_msg})
                return ToolMessage(content=error_msg, tool_call_id=tool_id)

            # 重试机制
            last_error = None
            for attempt in range(MAX_TOOL_RETRIES + 1):
                try:
                    result = await tool.ainvoke(tool_args)
                    result_str = result if isinstance(result, str) else str(result)
                    self.tool_trace.append({
                        "name": tool_name, "args": tool_args, "status": "ok", "attempt": attempt + 1,
                    })
                    logger.info("工具 %s 执行成功（第%d次尝试）", tool_name, attempt + 1)
                    return ToolMessage(content=result_str, tool_call_id=tool_id)
                except Exception as e:
                    last_error = e
                    logger.warning("工具 %s 第%d次执行失败: %s", tool_name, attempt + 1, e)
                    if attempt < MAX_TOOL_RETRIES:
                        await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避

            # 所有重试都失败
            error_msg = f"工具 {tool_name} 执行失败（重试{MAX_TOOL_RETRIES}次后仍失败）: {last_error}"
            logger.error(error_msg)
            self.tool_trace.append({"name": tool_name, "args": tool_args, "status": "failed", "error": str(last_error)})
            return ToolMessage(content=error_msg, tool_call_id=tool_id)

        # 并行执行所有工具调用
        return await asyncio.gather(*[execute_single(tc) for tc in tool_calls])
