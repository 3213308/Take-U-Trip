# app/models/intention.py
from pydantic import BaseModel, Field
from enum import Enum


class Intent(str, Enum):
    PLANNING = "planning"          # 完整多日行程规划
    NON_PLANNING = "non_planning"  # 非规划（信息查询/推荐/闲聊）


class NonPlanningAction(str, Enum):
    INFO_QUERY = "info_query"      # 提供信息（天气/景点/美食/交通）
    MODIFY = "modify"              # 修改已有规划
    CHAT = "chat"                  # 闲聊/能力咨询


class IntentionResult(BaseModel):
    """intake_node 的 LLM 结构化输出"""
    intent: Intent = Field(description="planning=要完整行程；non_planning=单点信息/闲聊/修改")
    action: NonPlanningAction = Field(description="非规划时的具体动作；planning 时填 chat")
    slots: dict = Field(
        default_factory=dict,
        description="从用户话里提取的槽位，如 {'destination': '成都', 'days': 2, 'budget': 2000}",
    )
    missing_slots: list[str] = Field(
        default_factory=list,
        description="planning 意图必填但用户没提供的槽位，如 ['destination', 'days']；非规划时留空",
    )
    clarify_question: str = Field(
        default="",
        description="planning 缺槽位时，向用户提问的原话；槽位齐或非规划时留空",
    )
