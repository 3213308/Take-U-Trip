import { useChatStore } from "@/stores/chatStore";
import type { PhaseName } from "@/types/chat";
import { clsx } from "clsx";
import { fmtMoney } from "@/lib/utils/cost";

const PHASES: { key: PhaseName; label: string; icon: string }[] = [
  { key: "memory_loaded", label: "加载记忆", icon: "🧠" },
  { key: "intake_done", label: "意图识别", icon: "🎯" },
  { key: "planner_done", label: "规划行程", icon: "🗓️" },
  { key: "budgeter_done", label: "核算预算", icon: "💰" },
  { key: "reviewer_done", label: "审查质量", icon: "🔍" },
  { key: "answer_done", label: "生成回复", icon: "💬" },
  { key: "finalizing", label: "生成结果", icon: "✨" },
];

export function AgentProcessPanel() {
  const phase = useChatStore((s) => s.phase);
  const toolTrace = useChatStore((s) => s.toolTrace);
  const sending = useChatStore((s) => s.sending);

  const currentIndex = phase ? PHASES.findIndex((p) => p.key === phase.phase) : -1;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-100 px-5 py-4">
        <h3 className="text-sm font-semibold text-slate-700">Agent 执行过程</h3>
        <p className="mt-0.5 text-xs text-slate-400">
          {sending
            ? "实时展示多 Agent 协作状态"
            : phase
              ? "上次执行记录"
              : "发送消息后开始展示"}
        </p>
      </div>

      {/* 阶段步骤条 */}
      <div className="border-b border-slate-100 px-5 py-4">
        <div className="space-y-1">
          {PHASES.map((p, i) => {
            const done = currentIndex > i;
            const active = currentIndex === i && sending;
            const wasActive = currentIndex === i && !sending;
            return (
              <div key={p.key} className="flex items-center gap-3 py-1">
                <div
                  className={clsx(
                    "flex h-6 w-6 items-center justify-center rounded-full text-[11px] transition-colors",
                    done && "bg-brand-100 text-brand-700",
                    active && "animate-pulse bg-brand-600 text-white",
                    wasActive && "bg-brand-600 text-white",
                    !done && !active && !wasActive && "bg-slate-100 text-slate-400",
                  )}
                >
                  {done ? "✓" : p.icon}
                </div>
                <div className="flex-1">
                  <div
                    className={clsx(
                      "text-xs font-medium",
                      active || wasActive || done ? "text-slate-700" : "text-slate-400",
                    )}
                  >
                    {p.label}
                    {p.key === "intake_done" && phase && (
                      <span className="ml-1.5 rounded-full bg-brand-100 px-1.5 py-0.5 text-[10px] text-brand-700">
                        {phase.intent === "planning" ? "规划" : "非规划"}
                        {phase.action && phase.action !== "chat" && `·${phase.action}`}
                      </span>
                    )}
                    {p.key === "planner_done" && phase && phase.round > 0 && (
                      <span className="ml-1.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">
                        第 {phase.round + 1} 轮
                      </span>
                    )}
                    {p.key === "reviewer_done" && phase?.phase === "reviewer_done" && phase.decision && (
                      <span
                        className={clsx(
                          "ml-1.5 rounded-full px-1.5 py-0.5 text-[10px]",
                          phase.decision === "approve"
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-amber-100 text-amber-700",
                        )}
                      >
                        {phase.decision === "approve" ? "通过" : "打回修订"}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* 预算数字条 */}
        {phase?.budget && (
          <div className="mt-3 grid grid-cols-3 gap-2 rounded-xl bg-slate-50 p-3 text-center">
            <div>
              <div className="text-[10px] text-slate-400">实际花费</div>
              <div className="text-xs font-semibold text-slate-700">
                {phase.budget.actual_total != null ? fmtMoney(phase.budget.actual_total) : "—"}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-slate-400">用户预算</div>
              <div className="text-xs font-semibold text-slate-700">
                {phase.budget.user_budget != null ? fmtMoney(phase.budget.user_budget) : "—"}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-slate-400">剩余</div>
              <div
                className={clsx(
                  "text-xs font-semibold",
                  (phase.budget.remaining ?? 0) < 0 ? "text-red-500" : "text-emerald-600",
                )}
              >
                {phase.budget.remaining != null ? fmtMoney(phase.budget.remaining) : "—"}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 工具调用轨迹 */}
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        <h4 className="mb-2 text-xs font-medium text-slate-400">
          工具调用（{toolTrace.length}）
        </h4>
        {toolTrace.length === 0 ? (
          <p className="text-xs text-slate-300">暂无工具调用</p>
        ) : (
          <div className="space-y-1.5">
            {toolTrace.map((t, i) => (
              <details key={i} className="group rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2">
                <summary className="flex cursor-pointer list-none items-center gap-2 text-xs">
                  <span
                    className={clsx(
                      "h-1.5 w-1.5 rounded-full",
                      t.status === "ok" ? "bg-emerald-400" : "bg-red-400",
                    )}
                  />
                  <span className="font-medium text-slate-700">{t.name}</span>
                  <span className="truncate text-slate-400">
                    {summarizeArgs(t.args)}
                  </span>
                </summary>
                <pre className="mt-2 overflow-x-auto rounded-md bg-white p-2 text-[11px] leading-relaxed text-slate-500">
                  {JSON.stringify(t.args, null, 2)}
                </pre>
              </details>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function summarizeArgs(args: Record<string, unknown>): string {
  const keys = Object.keys(args);
  if (!keys.length) return "";
  return keys
    .slice(0, 3)
    .map((k) => `${k}=${String(args[k]).slice(0, 20)}`)
    .join(" ");
}
