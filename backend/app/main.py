# app/main.py
"""FastAPI 应用入口

启动方式：uvicorn app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.chat import router as chat_router
from app.config import get_settings

from app.core.mcp_manager import close_mcp, init_mcp

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Take-U-Trip 后端启动 ===")
    logger.info("LLM Model: %s", settings.LLM_MODEL_NAME)
    logger.info("Adapter Mode: %s", settings.ADAPTER_MODE)
    await init_mcp()          # 启动时连接 MCP
    yield
    await close_mcp()         # 关闭时清理
    logger.info("=== 应用关闭 ===")


app = FastAPI(
    title="Take-U-Trip 智能旅游规划 API",
    version="0.1.0",
    description="基于 LangGraph + Function Calling 的旅游规划 Agent",
    lifespan=lifespan,
)

# CORS：开发阶段允许前端本地访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router)


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "take-u-trip", "version": "0.1.0"}
