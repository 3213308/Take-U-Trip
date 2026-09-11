# app/core/now.py
"""全局时间感知模块 — 统一提供当前日期，避免硬编码日期散落在各 prompt/工具里。

用法：
    from app.core.now import now, today_str, next_week_str, date_hint

    # 直接拿字符串
    today = today_str()          # "2026-09-11"
    next_week = next_week_str()  # "2026-09-18"

    # 拼到 prompt 里
    system_prompt = f"...{date_hint()}..."
"""

from datetime import date, timedelta


def today() -> date:
    return date.today()


def today_str() -> str:
    """今天 YYYY-MM-DD"""
    return today().isoformat()


def next_week_str() -> str:
    """一周后 YYYY-MM-DD（用户没给日期时的默认出发日）"""
    return (today() + timedelta(days=7)).isoformat()


def in_days_str(n: int) -> str:
    """n 天后 YYYY-MM-DD"""
    return (today() + timedelta(days=n)).isoformat()


def date_hint() -> str:
    """可直接拼进 system prompt 的日期说明"""
    return (
        f"今天是 {today_str()}（{today().strftime('%A')}）。"
        f"用户未指定日期时，默认从 {next_week_str()} 开始规划。"
        f"所有工具调用的日期参数必须是未来的真实日期，禁止使用 2025 年的示例日期。"
    )
