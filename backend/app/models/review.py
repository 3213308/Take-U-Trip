# app/models/review.py
"""审核员的结构化裁决结果"""

from pydantic import BaseModel, Field


class ReviewIssue(BaseModel):
    issue_type: str = Field(description="问题类型：工具漏调/无证据内容/预算错误/时间衔接/日期一致")
    detail: str = Field(description="具体问题描述，要指出是哪个活动、哪个数字")
    severity: str = Field(
        default="blocker",
        description="blocker=必须打回的硬伤（费用错误或缺失、时间冲突、关键数字无证据、工具漏调）；"
                    "minor=可选优化（措辞、松紧度、已标注估算的金额），不触发打回"
    )


class ReviewResult(BaseModel):
    decision: str = Field(description="approve=通过，revise=打回重做")
    issues: list[ReviewIssue] = Field(default_factory=list, description="发现的问题列表")
    feedback: str = Field(description="打回时给规划师的具体修改指令；通过时为空")
