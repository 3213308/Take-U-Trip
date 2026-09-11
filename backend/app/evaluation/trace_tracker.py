# app/evaluation/trace_tracker.py
"""轻量运行追踪器 —— 把一次多 Agent 运行按节点结构化。

UsageTracker 只管全局 token 总数；本追踪器回答：
哪个节点花了多久、吃了多少 token、调了哪些工具。
用于定位 case_003 成本瓶颈，以及结构化 None 发生在哪个节点。

识别节点的依据（经 callback 探测确认）：
- 节点层 chain 的 name == metadata["langgraph_node"]；
- 同节点内嵌套的 RunnableSequence / PydanticToolsParser / route_after_*
  虽带同一个 langgraph_node，但 name 不等于它，故用 name==node 过滤节点层。
- langgraph_step 在一次运行内单调递增，天然区分"planner 第几次进入"。
"""

import time

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class TraceTracker(BaseCallbackHandler):
    def __init__(self) -> None:
        self.spans: list[dict] = []
        self._current: dict | None = None   # 正在执行的节点 span
        self._seen_llm: set = set()         # run_id 去重
        self._current_run_id = None

    # ---------- 节点层 ----------
    def on_chain_start(self, serialized, inputs, **kwargs):
        meta = kwargs.get("metadata") or {}
        node = meta.get("langgraph_node")
        name = kwargs.get("name")
        if not node or name != node:
            return
        self._current_run_id = kwargs.get("run_id")
        self._current = {
            "step": meta.get("langgraph_step"),
            "node": node,
            "start": time.perf_counter(),
            "ms": 0.0,
            "llm_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "tools": [],
        }

    def on_chain_end(self, outputs, **kwargs):
        # 注意：on_chain_end 的 name 恒为 None，不能用 name 判断节点层；
        # 改用 run_id 与节点层 start 配对。嵌套子链 end 的 run_id 不同，不会误关。
        if self._current is not None and kwargs.get("run_id") == self._current_run_id:
            self._current["ms"] = round((time.perf_counter() - self._current["start"]) * 1000)
            self.spans.append(self._current)
            self._current = None
            self._current_run_id = None

    # ---------- 工具（归到当前节点） ----------
    def on_tool_end(self, output, **kwargs):
        if self._current is not None and kwargs.get("name"):
            self._current["tools"].append(kwargs["name"])

    # ---------- LLM token 按节点归组 ----------
    def on_llm_end(self, response: LLMResult, **kwargs):
        self._accumulate(response, kwargs)

    def on_chat_model_end(self, response: LLMResult, **kwargs):
        self._accumulate(response, kwargs)

    def _accumulate(self, response: LLMResult, kwargs) -> None:
        run_id = kwargs.get("run_id")
        if run_id is not None and run_id in self._seen_llm:
            return
        if run_id is not None:
            self._seen_llm.add(run_id)
        if self._current is None:           # 不在任何节点内，丢弃
            return
        try:
            message = response.generations[0][0].message
            usage = getattr(message, "usage_metadata", None)
            if usage is None:
                llm_output = getattr(response, "llm_output", None) or {}
                token_usage = llm_output.get("token_usage", {}) or {}
                usage = {
                    "input_tokens": token_usage.get("prompt_tokens", 0),
                    "output_tokens": token_usage.get("completion_tokens", 0),
                }
            self._current["llm_calls"] += 1
            self._current["input_tokens"] += usage.get("input_tokens", 0) or 0
            self._current["output_tokens"] += usage.get("output_tokens", 0) or 0
        except Exception:
            pass                            # 观测器异常不得影响主流程

    def print_report(self) -> None:
        print(f"{'step':>4}  {'node':<14} {'ms':>8} {'LLM':>4} {'in_tok':>9}  tools")
        for s in self.spans:
            print(f"{s['step']:>4}  {s['node']:<14} {s['ms']:>8.0f} "
                  f"{s['llm_calls']:>4} {s['input_tokens']:>9}  {','.join(s['tools'])}")
        print(f"\n合计 input_tokens = {sum(s['input_tokens'] for s in self.spans)}")
