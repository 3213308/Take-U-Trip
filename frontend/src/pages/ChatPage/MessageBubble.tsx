import type { ChatMessage } from "@/types/chat";
import { clsx } from "clsx";
import { ItineraryResultCard } from "./ItineraryResultCard";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={clsx("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={clsx(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm",
          isUser ? "bg-slate-200" : "bg-brand-600 text-white",
        )}
      >
        {isUser ? "我" : "AI"}
      </div>

      <div className={clsx("min-w-0 max-w-[80%]", isUser && "text-right")}>
        <div
          className={clsx(
            "inline-block rounded-2xl px-4 py-3 text-left text-sm leading-relaxed",
            isUser
              ? "rounded-tr-sm bg-brand-600 text-white"
              : "rounded-tl-sm border border-slate-100 bg-white text-slate-700 shadow-sm",
          )}
        >
          {message.error ? (
            <div className="text-red-600">
              <div className="mb-1 font-medium">请求出错</div>
              {message.error}
            </div>
          ) : (
            <>
              <p className="whitespace-pre-wrap">{message.content}</p>
              {message.itinerary && <ItineraryResultCard itinerary={message.itinerary} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
