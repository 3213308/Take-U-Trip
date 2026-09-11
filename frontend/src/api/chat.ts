import { consumeSSE } from "./sse";
import type {
  DoneEvent,
  ErrorEvent,
  FinalEvent,
  StatusEvent,
  ToolResultEvent,
} from "@/types/chat";

const API_BASE = "/api";

export interface StreamHandlers {
  onStatus?: (s: StatusEvent) => void;
  onToolResult?: (t: ToolResultEvent) => void;
  onFinal?: (f: FinalEvent) => void;
  onDone?: (d: DoneEvent) => void;
  onError?: (message: string) => void;
}

/** SSE 流式聊天。resolve 返回 done 事件的 thread_id；用户中断时 reject AbortError。 */
export async function streamChat(
  message: string,
  opts: { userId?: string; threadId?: string },
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<DoneEvent> {
  let doneEvent: DoneEvent | null = null;

  const resp = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      user_id: opts.userId ?? "default",
      thread_id: opts.threadId ?? "",
    }),
    signal,
  });

  await consumeSSE(
    resp,
    (type, data) => {
      switch (type) {
        case "status":
          handlers.onStatus?.(data as StatusEvent);
          break;
        case "tool_result":
          handlers.onToolResult?.(data as ToolResultEvent);
          break;
        case "final":
          handlers.onFinal?.(data as FinalEvent);
          break;
        case "done":
          doneEvent = data as DoneEvent;
          handlers.onDone?.(doneEvent);
          break;
        case "error":
          handlers.onError?.((data as ErrorEvent).message);
          break;
        default:
          console.warn("[chat] 未知事件类型", type, data);
      }
    },
    signal,
  );

  if (!doneEvent) {
    throw new Error("流意外结束，未收到完成事件");
  }
  return doneEvent;
}

/** 后端健康检查（Sidebar 状态点轮询） */
export async function checkHealth(): Promise<boolean> {
  try {
    const resp = await fetch(`/health`);
    return resp.ok;
  } catch {
    return false;
  }
}
