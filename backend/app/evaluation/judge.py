# app/evaluation/judge.py
"""LLM-as-Judge — 用 LLM 评估最终行程质量（语义层指标）"""

import json
import logging

from app.llm.client import get_llm

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """你是极其严格的旅游产品评审，默认怀疑答案质量。

用户需求：{user_input}
检查点：
{check_points}

【工具返回的真实数据】（以下是Agent实际查询到的数据，来源于此的数字不算编造）：
{tool_evidence}

待评审内容（{content_label}）：
{content}

评分锚点：
- 9-10：检查点全满足，所有具体数字都能在工具数据中找到依据，无矛盾
- 7-8：检查点全满足，有轻微瑕疵
- 5-6：满足大部分，有明显缺失或一处数据无工具依据
- 3-4：只满足一半，或存在工具数据之外的编造
- 1-2：基本未满足

判定编造的规则：只有当具体数字【既不在工具数据中、也不是简单求和计算】时，才算疑似编造。
工具数据里明确存在的价格/时间/评分，一律不算编造。

只输出严格 JSON：
{{
    "check_results": [{{"checkpoint": "检查点", "passed": true/false, "reason": "依据"}}],
    "weaknesses": ["缺点1", "缺点2"],
    "suspected_hallucinations": ["真正无工具依据的内容"],
    "score": 数字,
    "summary": "一句话总评"
}}"""


async def llm_judge(user_input: str, check_points: list[str],
                    itinerary: dict | None, answer: str = "",
                    tool_evidence: str = "") -> dict:
    llm = get_llm()

    if itinerary:
        content_label, content = "生成的行程", json.dumps(itinerary, ensure_ascii=False)[:6000]
    else:
        content_label, content = "助手的回答", answer or "（空回答）"

    check_text = "\n".join(f"{i+1}. {cp}" for i, cp in enumerate(check_points))
    prompt = JUDGE_PROMPT.format(
        user_input=user_input,
        check_points=check_text,
        tool_evidence=tool_evidence[:4000] or "（本次未调用工具）",
        content_label=content_label,
        content=content,
    )
    try:
        resp = llm.invoke(prompt)
        text = resp.content.strip()
        if text.startswith("```json"):
            text = text.removeprefix("```json").removesuffix("```").strip()
        return json.loads(text)
    except Exception as e:
        logger.warning("LLM Judge 解析失败: %s", e)
        return {"check_results": [], "score": -1, "summary": f"评估失败: {e}"}
