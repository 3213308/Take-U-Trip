import { useChatStore } from "@/stores/chatStore";
import { ChatThread } from "./ChatThread";
import { ChatInput } from "./ChatInput";
import { AgentProcessPanel } from "./AgentProcessPanel";

export function ChatPage() {
  return (
    <div className="flex h-full">
      {/* 左：聊天流 */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <ChatThread />
        </div>
        <div className="shrink-0 border-t border-slate-100 bg-white p-4">
          <ChatInput />
        </div>
      </div>

      {/* 右：Agent 过程面板（<xl 隐藏） */}
      <div className="hidden w-96 shrink-0 border-l border-slate-100 bg-white xl:block">
        <AgentProcessPanel />
      </div>
    </div>
  );
}
