/** 行程数据模型 — 严格对齐后端 app/models/itinerary.py 的 Pydantic 结构 */

export type ActivityCategory = "交通" | "景点" | "餐饮" | "住宿" | "自由活动";

export const ACTIVITY_CATEGORIES: ActivityCategory[] = [
  "交通",
  "景点",
  "餐饮",
  "住宿",
  "自由活动",
];

export interface Activity {
  /** 活动时间段，HH:MM-HH:MM */
  time: string;
  name: string;
  location: string;
  category: ActivityCategory;
  cost: number;
  notes: string;
  lng?: number | null;
  lat?: number | null;
}

export interface DayPlan {
  /** YYYY-MM-DD */
  date: string;
  theme: string;
  activities: Activity[];
  daily_budget: number;
}

export interface Itinerary {
  destination: string;
  days: number;
  total_budget: number;
  transport_cost: number;
  transport_suggestions: string[];
  accommodation_cost: number;
  food_cost: number;
  attraction_cost: number;
  days_plan: DayPlan[];
  warnings: string[];
}

/** 后端字段可能缺失时的兜底（旧数据 / 异常响应） */
export function normalizeItinerary(raw: Partial<Itinerary>): Itinerary | null {
  if (!raw || !raw.destination || !Array.isArray(raw.days_plan)) return null;
  return {
    destination: raw.destination,
    days: raw.days ?? raw.days_plan.length,
    total_budget: raw.total_budget ?? 0,
    transport_cost: raw.transport_cost ?? 0,
    transport_suggestions: raw.transport_suggestions ?? [],
    accommodation_cost: raw.accommodation_cost ?? 0,
    food_cost: raw.food_cost ?? 0,
    attraction_cost: raw.attraction_cost ?? 0,
    days_plan: raw.days_plan.map((d) => ({
      date: d.date ?? "",
      theme: d.theme ?? "",
      activities: (d.activities ?? []).map((a) => {
        const lng = a.lng != null ? Number(a.lng) : null;
        const lat = a.lat != null ? Number(a.lat) : null;
        return {
          time: a.time ?? "",
          name: a.name ?? "",
          location: a.location ?? "",
          category: (a.category ?? "自由活动") as ActivityCategory,
          cost: Number(a.cost ?? 0),
          notes: a.notes ?? "",
          lng: lng && !Number.isNaN(lng) ? lng : null,
          lat: lat && !Number.isNaN(lat) ? lat : null,
        };
      }),
      daily_budget: Number(d.daily_budget ?? 0),
    })),
    warnings: raw.warnings ?? [],
  };
}

export function createEmptyActivity(): Activity {
  return {
    time: "09:00-10:00",
    name: "",
    location: "",
    category: "自由活动",
    cost: 0,
    notes: "",
  };
}

export function createEmptyDay(date: string, index: number): DayPlan {
  return {
    date,
    theme: `第 ${index + 1} 天`,
    activities: [],
    daily_budget: 0,
  };
}
