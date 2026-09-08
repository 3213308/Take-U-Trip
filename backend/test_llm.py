"""测试 LLM 调用是否正常"""

from app.llm.client import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

llm = get_llm()

# 构造消息列表：SystemMessage 是系统提示，HumanMessage 是用户输入
messages = [
    SystemMessage(content="你是一个旅游助手，用简洁的语言回答。"),
    HumanMessage(content="你好，请用一句话介绍你自己。"),
]

print("正在调用 LLM...")
response = llm.invoke(messages)

# response 是 AIMessage 对象
print(f"\n回复内容: {response.content}")
print(f"回复类型: {type(response).__name__}")
print(f"是否有 tool_calls: {response.tool_calls}")
