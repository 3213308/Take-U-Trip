"""测试原生 Function Calling 完整闭环

流程：绑定工具 → 模型返回 tool_calls → 手动执行 → ToolMessage 回灌 → 模型生成最终答案
"""

import logging
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage

from app.llm.client import get_llm
from app.tools.weather import get_weather

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    llm = get_llm()

    # ===== 第1步：绑定工具 =====
    # bind_tools 会把工具的 JSON Schema 注入到模型的 function calling 上下文
    llm_with_tools = llm.bind_tools([get_weather])
    logger.info("工具已绑定: %s", [t.name for t in [get_weather]])

    # ===== 第2步：第一次调用模型 =====
    messages = [HumanMessage(content="北京今天天气怎么样？需要带伞吗？")]
    logger.info("第1次调用 LLM...")
    response: AIMessage = llm_with_tools.invoke(messages)

    logger.info("模型回复 content: %s", response.content)
    logger.info("模型返回 tool_calls: %s", response.tool_calls)

    # ===== 第3步：检查是否有工具调用 =====
    tool_calls = response.tool_calls
    if not tool_calls:
        logger.info("模型没有调用工具，直接返回最终答案")
        print(f"\n最终回答: {response.content}")
        return

    # ===== 第4步：执行工具并构造回灌消息 =====
    # 生产级：把 AIMessage 和 ToolMessage 都加入消息列表
    messages.append(response)

    for tc in tool_calls:
        logger.info("执行工具: name=%s, args=%s, id=%s", tc["name"], tc["args"], tc["id"])

        # 根据工具名分发执行（生产级会用工具注册表，这里简化）
        if tc["name"] == "get_weather":
            # tool.ainvoke 是异步调用，测试脚本里用同步方式调用
            import asyncio
            result = asyncio.run(get_weather.ainvoke(tc["args"]))
        else:
            result = f"未知工具: {tc['name']}"

        # 关键：ToolMessage 的 tool_call_id 必须和 tc["id"] 完全一致
        # 模型靠这个 id 把工具结果和之前的调用对应起来
        tool_msg = ToolMessage(content=result, tool_call_id=tc["id"])
        messages.append(tool_msg)
        logger.info("工具结果已回灌: %s", result[:50])

    # ===== 第5步：第二次调用模型 =====
    logger.info("第2次调用 LLM（带工具结果）...")
    final_response = llm_with_tools.invoke(messages)

    logger.info("最终回复 content: %s", final_response.content)
    logger.info("最终回复 tool_calls: %s", final_response.tool_calls)

    print("\n" + "=" * 60)
    print(f"最终回答: {final_response.content}")
    print("=" * 60)

    # 验证：正常情况下第二次调用没有 tool_calls
    if not final_response.tool_calls:
        print("\n✅ FC 闭环成功：模型看到工具结果后生成了最终答案，没有继续调用工具")
    else:
        print("\n⚠️ 模型还在调用工具，可能信息不够，需要继续循环")


if __name__ == "__main__":
    main()
