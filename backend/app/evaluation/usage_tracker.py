# app/evaluation/usage_tracker.py
"""统一 LLM 成本采集器 —— 单/多 Agent 成本对比的公平口径

单 Agent 旧做法是遍历 state.messages 的 usage_metadata，会漏掉多 Agent 中
不写进 messages 的调用（Planner 结构化、Reviewer 审查、偏好提取）。
本采集器通过 LangChain 回调，在图运行期间捕获所有 ChatModel 调用，
单/多两套图挂同一个采集器，成本口径天然一致。

只挂在"被测图"的 config.callbacks 上；LLM Judge 独立调用、不挂，故不计入。
"""

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class UsageTracker(BaseCallbackHandler):
    """累计一次图运行内所有聊天模型调用的次数与 token，按 run_id 去重。"""

    def __init__(self) -> None:
        self.llm_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._seen_run_ids: set = set()

    def _accumulate_once(self, response: LLMResult, run_id) -> None:
        # on_llm_end 与 on_chat_model_end 可能指向同一次调用，按 run_id 去重
        if run_id is not None and run_id in self._seen_run_ids:
            return
        if run_id is not None:
            self._seen_run_ids.add(run_id)

        self.llm_calls += 1
        try:
            message = response.generations[0][0].message
            usage = getattr(message, "usage_metadata", None)
            if usage is None:
                # 退回 OpenAI 原生 token_usage 字段
                llm_output = getattr(response, "llm_output", None) or {}
                token_usage = llm_output.get("token_usage", {}) or {}
                usage = {
                    "input_tokens": token_usage.get("prompt_tokens", 0),
                    "output_tokens": token_usage.get("completion_tokens", 0),
                }
            self.input_tokens += usage.get("input_tokens", 0) or 0
            self.output_tokens += usage.get("output_tokens", 0) or 0
        except Exception:
            # 采集器是旁路观测，任何异常都不得影响主流程
            pass

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        self._accumulate_once(response, kwargs.get("run_id"))

    def on_chat_model_end(self, response: LLMResult, **kwargs) -> None:
        self._accumulate_once(response, kwargs.get("run_id"))

    def snapshot(self) -> dict:
        """返回当前累计用量快照。"""
        return {
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
        }
