# app/memory/profile.py
"""从行程和对话中提取用户偏好"""

import json
import logging

from app.llm.client import get_llm

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """从以下用户对话和生成的行程中提取用户旅行偏好。

用户对话：
{user_text}

行程摘要：
{itinerary_text}

提取规则：
1. 用户明确说过的偏好优先（如"我喜欢历史古迹""不吃辣"）
2. 从行程的活动类型推断偏好（历史古迹多→历史古迹偏好）
3. 只提取明确体现的信息，不要猜测

请输出严格 JSON（不要输出其他内容）：
{{
    "dietary_restrictions": ["饮食禁忌"],
    "attraction_preferences": ["景点偏好：自然景观/历史古迹/购物/美食"],
    "avoid_categories": ["明确不喜欢的"],
    "typical_budget_range": [最低预算, 最高预算],
    "travel_style": "休闲/紧凑/亲子/穷游",
    "transport_preference": "飞机/高铁/自驾"
}}
没有信息的字段留空列表或空字符串。"""


def extract_preferences(itinerary: dict, user_text: str = "") -> dict:
    """用 LLM 从行程和用户对话中提取偏好"""
    llm = get_llm()

    itinerary_summary = {
        "destination": itinerary.get("destination"),
        "days": itinerary.get("days"),
        "total_budget": itinerary.get("total_budget"),
        "activity_categories": list(set(
            act["category"]
            for day in itinerary.get("days_plan", [])
            for act in day.get("activities", [])
        )),
        "activity_names": [
            act["name"]
            for day in itinerary.get("days_plan", [])
            for act in day.get("activities", [])
        ],
    }

    prompt = EXTRACT_PROMPT.format(
        user_text=user_text or "（无）",
        itinerary_text=json.dumps(itinerary_summary, ensure_ascii=False),
    )

    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        if text.startswith("```json"):
            text = text.removeprefix("```json").removesuffix("```").strip()
        prefs = json.loads(text)
        logger.info("偏好提取成功: %s", prefs)
        return prefs
    except Exception as e:
        logger.warning("偏好提取失败: %s", e)
        return {}
