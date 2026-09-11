// storage/http.ts
import type { Repository } from "./types";
import type { WishItem } from "@/types/wishlist";
import type { Itinerary } from "@/types/itinerary";
import { normalizeItinerary } from "@/types/itinerary";

const API = "/api";

// ===== 愿望清单 API（操作即保存，id 与后端一致） =====

interface BackendWish {
  id: number;
  name: string;
  category: string;
  city: string;
  note: string;
  checked: number;
  sort_order: number;
  created_at: string;
}

function toFrontend(b: BackendWish): WishItem {
  return {
    id: String(b.id),
    name: b.name,
    location: b.category || "",
    city: b.city || "",
    source: "manual",
    notes: b.note || "",
    completed: !!b.checked,
    completedAt: null,
    createdAt: b.created_at,
  };
}

export interface WishInput {
  name: string;
  location: string;
  city: string;
  notes?: string;
  source: WishItem["source"];
}

export const wishlistApi = {
  async load(): Promise<WishItem[]> {
    try {
      const res = await fetch(`${API}/wishlist`);
      if (!res.ok) return [];
      const data = await res.json();
      return (data.items || []).map(toFrontend);
    } catch (e) {
      console.warn("[wishlist] 加载失败", e);
      return [];
    }
  },

  /** 创建愿望，返回带后端 id 的条目；失败返回 null */
  async create(input: WishInput): Promise<WishItem | null> {
    try {
      const res = await fetch(`${API}/wishlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: input.name,
          category: input.location || "",
          city: input.city || "",
          note: input.notes || "",
        }),
      });
      if (!res.ok) return null;
      const { id } = await res.json();
      return {
        id: String(id),
        name: input.name,
        location: input.location,
        city: input.city,
        source: input.source,
        notes: input.notes,
        completed: false,
        completedAt: null,
        createdAt: new Date().toISOString(),
      };
    } catch (e) {
      console.warn("[wishlist] 创建失败", e);
      return null;
    }
  },

  async update(id: string, patch: { checked?: boolean }): Promise<boolean> {
    try {
      const res = await fetch(`${API}/wishlist/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      return res.ok;
    } catch (e) {
      console.warn("[wishlist] 更新失败", e);
      return false;
    }
  },

  async remove(id: string): Promise<boolean> {
    try {
      const res = await fetch(`${API}/wishlist/${id}`, { method: "DELETE" });
      return res.ok;
    } catch (e) {
      console.warn("[wishlist] 删除失败", e);
      return false;
    }
  },
};

// ===== 聊天历史（从后端 checkpoint 恢复） =====

import type { ChatMessage } from "@/types/chat";

export const chatApi = {
  async loadHistory(threadId: string): Promise<{ role: string; content: string }[]> {
    try {
      const res = await fetch(`${API}/chat/history?thread_id=${encodeURIComponent(threadId)}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.messages || [];
    } catch {
      return [];
    }
  },
};

// ===== 行程 HTTP 仓库（只读） =====

export class ItineraryHttpRepo implements Repository<Itinerary | null> {
  async load(): Promise<Itinerary | null> {
    try {
      const res = await fetch(`${API}/itinerary/latest`);
      if (!res.ok) return null;
      const data = await res.json();
      return normalizeItinerary(data.itinerary);
    } catch {
      return null;
    }
  }

  async save(_data: Itinerary | null): Promise<void> {
    // 行程由后端 agent 自动保存，前端不主动写
  }

  async clear(): Promise<void> {}
}
