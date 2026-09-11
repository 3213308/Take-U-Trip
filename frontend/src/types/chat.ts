import type { Itinerary } from "./itinerary";

/** SSE 事件类型 — 对齐 backend/app/api/routes/chat.py 的事件契约 */

export type PhaseName =
  | "memory_loaded"
  | "intake_done"
  | "planner_done"
  | "budgeter_done"
  | "reviewer_done"
  | "answer_done"
  | "finalizing";

export interface StatusEvent {
  phase: PhaseName;
  profile_fields?: number;
  round?: number;
  is_planning?: boolean;
  tool_count?: number;
  actual_total?: number;
  user_budget?: number;
  remaining?: number;
  decision?: string;
  intent?: string;
  action?: string;
}

export interface ToolResultEvent {
  name: string;
  args: Record<string, unknown>;
  status: string;
}

export interface FinalEvent {
  answer: string;
  itinerary: Itinerary | null;
  tool_trace: ToolResultEvent[];
  forced_stop: boolean;
  is_planning: boolean;
}

export interface DoneEvent {
  thread_id: string;
}

export interface ErrorEvent {
  message: string;
}

export type ChatEventType = "status" | "tool_result" | "final" | "done" | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** 该条助手消息最终产出的行程（仅规划消息有） */
  itinerary: Itinerary | null;
  is_planning: boolean;
  /** 出错信息 */
  error?: string;
  createdAt: number;
}
