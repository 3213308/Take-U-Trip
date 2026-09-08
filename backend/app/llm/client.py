# app/llm/client.py
"""LLM 客户端封装 — 单例模式，整个项目共享一个 LLM 实例"""

from langchain_openai import ChatOpenAI

from app.config import get_settings

_llm = None

def get_llm() -> ChatOpenAI:
    """获取 LLM 实例（单例）"""
    global _llm
    if _llm is None:
        settings = get_settings()
        _llm = ChatOpenAI(
            model=settings.LLM_MODEL_NAME,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            temperature=0.3,  # 旅游规划需要一定创造性，但不要太高
        )
    return _llm