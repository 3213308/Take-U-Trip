import { useRef, useState, type KeyboardEvent } from "react";
import { useChatStore } from "@/stores/chatStore";

export function ChatInput() {
  const [text, setText] = useState("");
  const send = useChatStore((s) => s.send);
  const sending = useChatStore((s) => s.sending);
  const stop = useChatStore((s) => s.stop);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const doSend = () => {
    const t = text.trim();
    if (!t || sending) return;
    setText("");
    void send(t);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
  };

  return (
    <div className="mx-auto flex max-w-3xl items-end gap-2">
      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        rows={Math.min(4, Math.max(1, text.split("\n").length))}
        placeholder="描述你的旅行需求，如：成都3日游，预算2500，喜欢美食和熊猫…"
        className="max-h-32 flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-brand-400 focus:bg-white"
      />
      {sending ? (
        <button
          onClick={stop}
          className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-xl bg-red-500 text-white transition-colors hover:bg-red-600"
          title="停止生成"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        </button>
      ) : (
        <button
          onClick={doSend}
          disabled={!text.trim()}
          className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-xl bg-brand-600 text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-200"
          title="发送"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m22 2-7 20-4-9-9-4Z" />
            <path d="M22 2 11 13" />
          </svg>
        </button>
      )}
    </div>
  );
}
