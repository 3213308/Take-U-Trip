import { useEffect, useRef } from "react";
import { useChatStore } from "@/stores/chatStore";
import { MessageBubble } from "./MessageBubble";
import { SuggestionChips } from "./SuggestionChips";

export function ChatThread() {
  const messages = useChatStore((s) => s.messages);
  const hydrated = useChatStore((s) => s.hydrated);
  const sending = useChatStore((s) => s.sending);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, sending, messages[messages.length - 1]?.content]);

  if (!hydrated) {
    return <div className="p-8 text-sm text-slate-300">加载中…</div>;
  }

  if (messages.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-6 px-8">
        <div className="text-center">
          <div className="mb-3 text-5xl">🧳</div>
          <h2 className="text-xl font-bold text-slate-800">让 AI 为你规划一次完美旅行</h2>
          <p className="mt-2 text-sm text-slate-400">
            告诉我目的地、天数与预算，Agent 会调用工具查天气、选景点、算预算，生成一份可在地图上查看的行程
          </p>
        </div>
        <SuggestionChips />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-6 py-6">
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      {sending && messages[messages.length - 1]?.role === "assistant" && !messages[messages.length - 1]?.content && (
        <div className="flex items-center gap-2 pl-1 text-sm text-slate-400">
          <span className="flex gap-1">
            <i className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300 [animation-delay:0ms]" />
            <i className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300 [animation-delay:150ms]" />
            <i className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300 [animation-delay:300ms]" />
          </span>
          Agent 思考中…
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
