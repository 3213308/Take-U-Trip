import { useChatStore } from "@/stores/chatStore";

const SUGGESTIONS = [
  "帮我规划成都3日游，预算2500元",
  "北京2日游，重点美食和博物馆",
  "上海周末游，交通怎么选？",
];

export function SuggestionChips() {
  const send = useChatStore((s) => s.send);
  const sending = useChatStore((s) => s.sending);

  return (
    <div className="flex flex-wrap justify-center gap-2">
      {SUGGESTIONS.map((s) => (
        <button
          key={s}
          disabled={sending}
          className="cursor-pointer rounded-full border border-slate-200 bg-white px-4 py-2 text-xs text-slate-600 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:cursor-not-allowed"
          onClick={() => void send(s)}
        >
          {s}
        </button>
      ))}
    </div>
  );
}
