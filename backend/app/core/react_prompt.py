# app/core/react_prompt.py
"""手写 ReAct 循环（Prompt 版）— 纯文本协议

ReAct 的本质：Reasoning + Acting
模型在每轮输出 Thought（思考）和 Action（行动），
代码解析 Action 执行工具，把 Observation（观察结果）拼回去，
循环直到模型输出 Final Answer。

和原生 FC 版的区别：
- FC 版：模型用结构化的 tool_calls 字段调用工具，协议由 API 层定义
- Prompt 版：模型用纯文本输出 Thought/Action，协议由 prompt 定义，代码手动解析

为什么还要学 Prompt 版？
1. 理解 ReAct 原理，FC 只是它的一种实现
2. 有些模型不支持 function calling，只能用 Prompt 版
3. 便于对比两种工具调用协议的适用边界
"""

import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import get_llm
from app.tools import get_tool_map

logger = logging.getLogger(__name__)

# ReAct System Prompt — 定义文本协议
REACT_SYSTEM_PROMPT = """你是一个智能助手，必须使用工具来回答问题，禁止凭记忆直接回答。

你必须严格按照以下格式思考和行动：

Thought: 你对当前问题的分析
Action: 工具名(参数1=值1, 参数2=值2)
Observation: 工具执行的结果（由系统提供）
...（重复直到信息足够）

Thought: 我已经收集到足够的信息
Final Answer: 你的最终回答

【可用工具】
{tool_descriptions}

【示例】
Question: 北京天气怎么样？
Thought: 用户问北京天气，我需要调用 get_weather 工具查询
Action: get_weather(city=北京)
Observation: 北京：晴，气温10~22℃，北风3级
Thought: 我已经获取了北京的天气信息，可以回答了
Final Answer: 北京今天晴，10~22℃，北风3级。

【严格规则】
1. 必须先调用工具获取信息，禁止不调用工具直接输出 Final Answer
2. 每次只能调用一个工具
3. Action 格式必须是：工具名(参数=值)
4. 不要在 Observation 行写任何内容
5. 如果问题涉及实时信息（天气、景点等），必须调用工具"""



class PromptReActLoop:
    """Prompt 版 ReAct 循环"""

    def __init__(self, max_iterations: int = 8):
        self.llm = get_llm()
        self.tool_map = get_tool_map()
        self.max_iterations = max_iterations
        self.tool_trace: list[dict[str, Any]] = []

    def _build_tool_descriptions(self) -> str:
        """构建工具描述文本，注入 system prompt"""
        lines = []
        for name, tool in self.tool_map.items():
            # 从工具的 args_schema 提取参数信息
            schema = tool.args_schema
            params = []
            if schema and hasattr(schema, "model_fields"):
                for field_name, field in schema.model_fields.items():
                    desc = field.description or ""
                    required = field.is_required()
                    params.append(f"{field_name}{'*' if required else ''}: {desc}")
            param_str = ", ".join(params) if params else "无参数"
            lines.append(f"- {name}: {tool.description} 参数：{param_str}")
        return "\n".join(lines)

    def _parse_action(self, text: str) -> tuple[str, dict] | None:
        """从模型输出中解析 Action 行

        支持的格式：
        - Action: tool_name(param1=value1, param2=value2)
        - Action: tool_name(param1="value1")
        """
        # 匹配 Action: 工具名(参数)
        match = re.search(r"Action:\s*(\w+)\((.*?)\)", text, re.DOTALL)
        if not match:
            return None

        tool_name = match.group(1)
        args_str = match.group(2).strip()

        # 解析参数
        args: dict[str, str] = {}
        if args_str:
            # 简单解析：param=value, param=value
            # 生产级应该用更健壮的解析器，这里够用
            for part in re.split(r",(?![^()]*\))", args_str):
                if "=" in part:
                    key, value = part.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    args[key] = value

        return tool_name, args

    def _extract_thought(self, text: str) -> str:
        """提取 Thought 内容"""
        match = re.search(r"Thought:\s*(.+?)(?=\nAction:|\nFinal Answer:|$)", text, re.DOTALL)
        return match.group(1).strip() if match else ""


    async def run(self, user_message: str) -> dict[str, Any]:
        """执行 Prompt 版 ReAct 循环"""
        self.tool_trace = []
        tool_descriptions = self._build_tool_descriptions()
        system_prompt = REACT_SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)

        # 用纯文本拼接 conversation，而不是 messages 列表
        # 因为 Prompt 版 ReAct 依赖特定的文本格式
        conversation = f"{system_prompt}\n\nQuestion: {user_message}\n"

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            logger.info("=== Prompt ReAct 第 %d/%d 轮 ===", iteration, self.max_iterations)

            # 调用模型
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=conversation),
            ])
            output = response.content
            logger.info("模型输出:\n%s", output)

        # 保护：第一轮没调工具就输出 Final Answer，强制回去调工具
            if iteration == 1 and not self.tool_trace and "Final Answer:" in output:
                logger.warning("模型第一轮未调用工具直接回答，强制要求调用工具")
                conversation += f"\n{output}\nObservation: 你还没有调用任何工具，必须先调用工具获取真实信息，禁止凭记忆回答。请重新输出 Thought 和 Action。\n"
                continue

            # 检查是否是 Final Answer
            if "Final Answer:" in output:
                final_match = re.search(r"Final Answer:\s*(.+)", output, re.DOTALL)
                final_answer = final_match.group(1).strip() if final_match else output
                logger.info("模型输出 Final Answer，循环结束")
                return {
                    "final_answer": final_answer,
                    "tool_trace": self.tool_trace,
                    "iterations": iteration,
                    "raw_output": output,
                }

            # 解析 Action
            parsed = self._parse_action(output)
            if parsed is None:
                logger.warning("无法解析 Action，模型输出格式不对，追加提示让它重试")
                conversation += f"\n{output}\nObservation: 无法解析你的 Action，请严格按照格式输出：Action: 工具名(参数=值)\n"
                continue

            tool_name, tool_args = parsed
            thought = self._extract_thought(output)
            logger.info("Thought: %s", thought[:100])
            logger.info("Action: %s(%s)", tool_name, tool_args)

            # 执行工具
            tool = self.tool_map.get(tool_name)
            if tool is None:
                observation = f"错误：未知工具 '{tool_name}'，可用工具：{', '.join(self.tool_map.keys())}"
                self.tool_trace.append({"name": tool_name, "args": tool_args, "status": "unknown_tool"})
            else:
                try:
                    result = await tool.ainvoke(tool_args)
                    observation = result if isinstance(result, str) else str(result)
                    self.tool_trace.append({"name": tool_name, "args": tool_args, "status": "ok"})
                except Exception as e:
                    observation = f"工具执行错误：{str(e)}"
                    self.tool_trace.append({"name": tool_name, "args": tool_args, "status": "error", "error": str(e)})

            logger.info("Observation: %s", observation[:100])

            # 把模型输出和 Observation 拼回 conversation
            conversation += f"\n{output}\nObservation: {observation}\n"

        # 达到最大步数
        logger.warning("达到最大迭代次数 %d", self.max_iterations)
        return {
            "final_answer": "（达到最大思考步数）",
            "tool_trace": self.tool_trace,
            "iterations": iteration,
            "forced_stop": True,
        }
