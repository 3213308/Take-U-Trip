import { create } from "zustand";
import { streamChat } from "@/api/chat";
import type { ChatMessage, PhaseName, StatusEvent, ToolResultEvent } from "@/types/chat";
import { normalizeItinerary } from "@/types/itinerary";
import { genId } from "@/lib/utils/id";
import { useItineraryStore } from "./itineraryStore";

export interface PhaseInfo {
  phase: PhaseName;
  round: number;
  is_planning: boolean;
  budget?: { actual_total?: number; user_budget?: number; remaining?: number };
  decision?: string;
  intent?: string;
  action?: string;
}

interface ChatState {
  messages: ChatMessage[];
  threadId: string;
  sending: boolean;
  hydrated: boolean;

  /** 过程面板状态（不持久化） */
  phase: PhaseInfo | null;
  toolTrace: ToolResultEvent[];

  hydrate: (data: { messages: ChatMessage[]; threadId: string } | null) => void;
  send: (message: string) => Promise<void>;
  stop: () => void;
  clear: () => void;
}

let abortController: AbortController | null = null;

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  threadId: "",
  sending: false,
  hydrated: false,
  phase: null,
  toolTrace: [],

  hydrate: (data) =>
    set({
      messages: data?.messages ?? [],
      threadId: data?.threadId ?? "",
      hydrated: true,
    }),

  send: async (message) => {
    if (get().sending) return;

    const userMsg: ChatMessage = {
      id: genId(),
      role: "user",
      content: message,
      itinerary: null,
      is_planning: false,
      createdAt: Date.now(),
    };
    const assistantMsgId = genId();
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      itinerary: null,
      is_planning: false,
      createdAt: Date.now(),
    };

    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      sending: true,
      phase: null,
      toolTrace: [],
    }));

    const patchAssistant = (patch: Partial<ChatMessage>) =>
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === assistantMsgId ? { ...m, ...patch } : m,
        ),
      }));

    abortController = new AbortController();
    const { threadId } = get();

    try {
      const done = await streamChat(
        message,
        { threadId: threadId || undefined },
        {
          onStatus: (st: StatusEvent) => {
            if (st.phase === "budgeter_done") {
              set((s) => ({
                phase: s.phase
                  ? {
                      ...s.phase,
                      phase: st.phase,
                      budget: {
                        actual_total: st.actual_total,
                        user_budget: st.user_budget,
                        remaining: st.remaining,
                      },
                    }
                  : {
                      phase: st.phase,
                      round: st.round ?? 0,
                      is_planning: st.is_planning ?? true,
                      budget: {
                        actual_total: st.actual_total,
                        user_budget: st.user_budget,
                        remaining: st.remaining,
                      },
                    },
              }));
              return;
            }
            set((s) => ({
              phase: {
                phase: st.phase,
                round: st.round ?? s.phase?.round ?? 0,
                is_planning: st.is_planning ?? s.phase?.is_planning ?? true,
                decision: st.decision,
                intent: st.intent,
                action: st.action,
              },
            }));
          },

          onToolResult: (t) => set((s) => ({ toolTrace: [...s.toolTrace, t] })),

          onFinal: (f) => {
            const it = f.itinerary ? normalizeItinerary(f.itinerary) : null;
            patchAssistant({
              content: f.answer,
              itinerary: it,
              is_planning: f.is_planning,
            });
            if (it) {
              useItineraryStore.getState().setItinerary(it);
            }
          },

          onError: (msg) => {
            patchAssistant({ error: msg, content: msg });
          },
        },
        abortController.signal,
      );

      set({ threadId: done.thread_id });
      localStorage.setItem("tut:v1:threadId", done.thread_id);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        const last = get().messages.find((m) => m.id === assistantMsgId);
        patchAssistant({ content: last?.content || "已停止生成" });
      } else {
        const msg = e instanceof Error ? e.message : "请求失败，请检查后端服务";
        patchAssistant({ error: msg });
      }
    } finally {
      abortController = null;
      set({ sending: false });
    }
  },

  stop: () => {
    abortController?.abort();
  },

  clear: () => set({ messages: [], threadId: "", phase: null, toolTrace: [] }),
}));
