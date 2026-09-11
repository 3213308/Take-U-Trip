import type { Activity, ActivityCategory, Itinerary } from "@/types/itinerary";

/** 活动费用总和（不含后端分类预算字段，纯按活动计算） */
export function sumActivitiesCost(it: Itinerary): number {
  return it.days_plan.reduce(
    (sum, d) => sum + d.activities.reduce((s, a) => s + (Number(a.cost) || 0), 0),
    0,
  );
}

export function dayCost(activities: Activity[]): number {
  return activities.reduce((s, a) => s + (Number(a.cost) || 0), 0);
}

/** 按分类小计 */
export function costsByCategory(it: Itinerary): Record<ActivityCategory, number> {
  const acc: Record<ActivityCategory, number> = {
    交通: 0,
    景点: 0,
    餐饮: 0,
    住宿: 0,
    自由活动: 0,
  };
  for (const d of it.days_plan) {
    for (const a of d.activities) {
      acc[a.category] += Number(a.cost) || 0;
    }
  }
  return acc;
}

export function fmtMoney(n: number): string {
  return `¥${(Number(n) || 0).toLocaleString("zh-CN", {
    maximumFractionDigits: 0,
  })}`;
}
