/** 日期工具 — 行程日期均为 "YYYY-MM-DD" 字符串 */

export function formatDateCN(dateStr: string): string {
  if (!dateStr) return "";
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return dateStr;
  const week = new Intl.DateTimeFormat("zh-CN", { weekday: "short" }).format(d);
  const md = `${d.getMonth() + 1}月${d.getDate()}日`;
  return `${md} ${week}`;
}

/** 顺延 n 天，返回 YYYY-MM-DD */
export function addDays(dateStr: string, n: number): string {
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return dateStr;
  d.setDate(d.getDate() + n);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function todayStr(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** "HH:MM" → 当天分钟数 */
export function hmToMinutes(hm: string): number {
  const [h, m] = hm.split(":").map(Number);
  if (Number.isNaN(h) || Number.isNaN(m)) return 0;
  return h * 60 + m;
}

/** "HH:MM-HH:MM" → {start, end} 分钟数 */
export function parseTimeRange(time: string): { start: number; end: number } {
  const [s, e] = time.split("-").map((t) => hmToMinutes(t.trim()));
  return { start: s ?? 0, end: e ?? s ?? 0 };
}

/** 判断当前时刻是否处于某个活动时间段内（含跨天不处理，仅当天比较） */
export function isNowInRange(time: string, nowMinutes: number): boolean {
  const { start, end } = parseTimeRange(time);
  if (!start && !end) return false;
  if (end < start) return nowMinutes >= start || nowMinutes < end; // 跨零点
  return nowMinutes >= start && nowMinutes < end;
}
