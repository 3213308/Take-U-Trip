/**
 * 数据访问抽象层 — 所有领域数据的读写统一走 Repository 接口。
 * 当前实现：localStorage（storage/local.ts）
 * 未来切换：HTTP 实现（storage/http.ts），store 与页面代码零改动。
 */
export interface Repository<T> {
  /** 读取数据；不存在或损坏时返回 null */
  load(): Promise<T | null>;
  save(data: T): Promise<void>;
  clear(): Promise<void>;
}
