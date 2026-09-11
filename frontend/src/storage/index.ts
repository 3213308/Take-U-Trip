import type { Repository } from "./types";
import type { Itinerary } from "@/types/itinerary";
import { itineraryRepo, mapRepo } from "./repositories";
import { wishlistApi, chatApi } from "./http";
import { useItineraryStore } from "@/stores/itineraryStore";
import { useWishlistStore } from "@/stores/wishlistStore";
import { useChatStore } from "@/stores/chatStore";
import { useMapStore } from "@/stores/mapStore";

export type { Repository };

/**
 * 将 store 绑定到仓库：启动时 hydrate，之后状态变化防抖自动保存，
 * 页面关闭（pagehide）时 flush 未落盘的最后一次变更。
 */
export function bindStoreToRepository<T>(opts: {
  hydrate: (data: T | null) => void;
  repo: Repository<T>;
  getSnapshot: () => T;
  subscribe: (listener: () => void) => () => void;
  debounceMs?: number;
}): () => void {
  const { hydrate, repo, getSnapshot, subscribe, debounceMs = 300 } = opts;

  let hydrated = false;
  let pendingTimer: ReturnType<typeof setTimeout> | null = null;
  let lastSaved = "";

  const flush = async () => {
    if (pendingTimer) {
      clearTimeout(pendingTimer);
      pendingTimer = null;
    }
    if (!hydrated) return;
    const snapshot = getSnapshot();
    const json = JSON.stringify(snapshot);
    if (json === lastSaved) return;
    lastSaved = json;
    try {
      await repo.save(snapshot);
    } catch (e) {
      console.warn("[storage] 保存失败", e);
    }
  };

  const onPageHide = () => {
    void flush();
  };

  (async () => {
    const data = await repo.load();
    hydrate(data);
    hydrated = true;
    lastSaved = JSON.stringify(getSnapshot());
    window.addEventListener("pagehide", onPageHide);
  })();

  const unsubscribe = subscribe(() => {
    if (!hydrated) return;
    if (pendingTimer) clearTimeout(pendingTimer);
    pendingTimer = setTimeout(() => {
      void flush();
    }, debounceMs);
  });

  return () => {
    unsubscribe();
    window.removeEventListener("pagehide", onPageHide);
    void flush();
  };
}

/** 应用启动时绑定全部领域数据 */
export function bindAllStores(): () => void {
  const unbinders = [
    bindStoreToRepository<Itinerary | null>({
      hydrate: useItineraryStore.getState().hydrate,
      repo: itineraryRepo,
      getSnapshot: () => useItineraryStore.getState().itinerary,
      subscribe: (fn) => useItineraryStore.subscribe(fn),
    }),
    bindStoreToRepository({
      hydrate: useMapStore.getState().hydrate,
      repo: mapRepo,
      getSnapshot: () => {
        const { selectedDayIndex, panelCollapsed, geocodeCache } = useMapStore.getState();
        return { selectedDayIndex, panelCollapsed, geocodeCache };
      },
      subscribe: (fn) => useMapStore.subscribe(fn),
    }),
  ];
  // 聊天历史：从后端 checkpoint 恢复（threadId 存 localStorage）
  (async () => {
    const threadId = localStorage.getItem("tut:v1:threadId") || "";
    if (!threadId) {
      useChatStore.getState().hydrate(null);
      return;
    }
    const msgs = await chatApi.loadHistory(threadId);
    useChatStore.getState().hydrate({
      threadId,
      messages: msgs.map((m, i) => ({
        id: String(i),
        role: m.role as "user" | "assistant",
        content: m.content,
        itinerary: null,
        is_planning: false,
        createdAt: Date.now(),
      })),
    });
  })();
  // 愿望清单启动时从后端拉取
  (async () => {
    const items = await wishlistApi.load();
    useWishlistStore.getState().hydrate(items);
  })();

  return () => unbinders.forEach((u) => u());
}
