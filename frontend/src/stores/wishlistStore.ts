import { create } from "zustand";
import type { WishItem } from "@/types/wishlist";
import { wishlistApi, type WishInput } from "@/storage/http";

export interface WishStats {
  total: number;
  completed: number;
  byCity: { city: string; total: number; completed: number }[];
}

interface WishlistState {
  items: WishItem[];
  hydrated: boolean;
  hydrate: (data: WishItem[] | null) => void;

  add: (input: WishInput) => Promise<void>;
  remove: (id: string) => Promise<void>;
  toggle: (id: string) => Promise<void>;
  /** 批量导入，按 name+city 去重（已存在的跳过），返回实际新增数 */
  importMany: (inputs: WishInput[]) => Promise<number>;
}

export function selectStats(items: WishItem[]): WishStats {
  const completed = items.filter((i) => i.completed).length;
  const cityMap = new Map<string, { total: number; completed: number }>();
  for (const i of items) {
    const c = cityMap.get(i.city) ?? { total: 0, completed: 0 };
    c.total += 1;
    if (i.completed) c.completed += 1;
    cityMap.set(i.city, c);
  }
  const byCity = [...cityMap.entries()]
    .map(([city, v]) => ({ city, ...v }))
    .sort((a, b) => b.total - a.total);
  return { total: items.length, completed, byCity };
}

export const useWishlistStore = create<WishlistState>((set, get) => ({
  items: [],
  hydrated: false,

  hydrate: (data) => set({ items: data ?? [], hydrated: true }),

  add: async (input) => {
    const item = await wishlistApi.create(input);
    if (!item) {
      console.warn("[wishlist] 添加失败，请检查后端服务");
      return;
    }
    set((s) => ({ items: [...s.items, item] }));
  },

  remove: async (id) => {
    const prev = get().items;
    set((s) => ({ items: s.items.filter((i) => i.id !== id) }));
    const ok = await wishlistApi.remove(id);
    if (!ok) {
      set({ items: prev });
    }
  },

  toggle: async (id) => {
    const item = get().items.find((i) => i.id === id);
    if (!item) return;
    const next = {
      ...item,
      completed: !item.completed,
      completedAt: !item.completed ? new Date().toISOString() : null,
    };
    set((s) => ({ items: s.items.map((i) => (i.id === id ? next : i)) }));
    const ok = await wishlistApi.update(id, { checked: next.completed });
    if (!ok) {
      // 保存失败回滚，避免前后端状态不一致
      set((s) => ({ items: s.items.map((i) => (i.id === id ? item : i)) }));
    }
  },

  importMany: async (inputs) => {
    const existing = new Set(get().items.map((i) => `${i.name}::${i.city}`));
    const fresh = inputs.filter((i) => !existing.has(`${i.name}::${i.city}`));
    let added = 0;
    for (const input of fresh) {
      const item = await wishlistApi.create(input);
      if (item) {
        set((s) => ({ items: [...s.items, item] }));
        added++;
      }
    }
    return added;
  },
}));
