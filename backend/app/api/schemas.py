# app/api/schemas.py
"""API 请求/响应数据模型"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(description="用户消息")
    user_id: str = Field(default="default", description="用户ID")
    thread_id: str = Field(default="", description="会话线程ID，为空则新建")


class ToolEvent(BaseModel):
    """工具调用事件"""
    name: str
    args: dict
    status: str = "ok"


class ChatResponse(BaseModel):
    """非流式响应"""
    thread_id: str
    answer: str
    itinerary: dict | None = None
    tool_trace: list[dict] = []
