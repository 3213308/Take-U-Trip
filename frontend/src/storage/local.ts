import type { Repository } from "./types";

interface Envelope<T> {
  v: number;
  savedAt: string;
  data: T;
}

/**
 * localStorage 实现：信封格式 { v, savedAt, data }，
 * 带版本检查与损坏容错（坏数据视为不存在，避免白屏）。
 */
export function createJSONRepository<T>(opts: {
  key: string;
  version?: number;
  migrate?: (raw: unknown) => T;
}): Repository<T> {
  const { key, version = 1, migrate } = opts;

  return {
    async load(): Promise<T | null> {
      try {
        const raw = localStorage.getItem(key);
        if (!raw) return null;
        const parsed = JSON.parse(raw) as Envelope<T>;
        if (!parsed || parsed.v !== version) {
          if (migrate) return migrate(parsed);
          return null;
        }
        return parsed.data as T;
      } catch (e) {
        console.warn(`[storage] 读取 ${key} 失败，视为无数据`, e);
        return null;
      }
    },

    async save(data: T): Promise<void> {
      const envelope: Envelope<T> = {
        v: version,
        savedAt: new Date().toISOString(),
        data,
      };
      localStorage.setItem(key, JSON.stringify(envelope));
    },

    async clear(): Promise<void> {
      localStorage.removeItem(key);
    },
  };
}
