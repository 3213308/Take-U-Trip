"""应用配置 — pydantic-settings 自动从 .env 读取"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # model_config 告诉 pydantic-settings 从 .env 文件读配置
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL_NAME: str = "deepseek-chat"

    # 服务
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # 适配器
    ADAPTER_MODE: str = "mock"

    # 数据库
    DB_URL: str = "sqlite:///./take_u_trip.db"

    # ReAct
    MAX_ITERATIONS: int = 8

    # 缓存
    TOOL_CACHE_TTL: int = 3600


# 单例：整个项目共享一个 Settings 实例
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings