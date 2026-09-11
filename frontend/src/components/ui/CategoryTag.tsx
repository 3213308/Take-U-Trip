import { clsx } from "clsx";
import type { ActivityCategory } from "@/types/itinerary";

const catCls: Record<ActivityCategory, string> = {
  交通: "bg-blue-50 text-blue-600 border-blue-200",
  景点: "bg-emerald-50 text-emerald-600 border-emerald-200",
  餐饮: "bg-amber-50 text-amber-600 border-amber-200",
  住宿: "bg-violet-50 text-violet-600 border-violet-200",
  自由活动: "bg-slate-100 text-slate-500 border-slate-200",
};

export const CATEGORY_DOT: Record<ActivityCategory, string> = {
  交通: "bg-cat-transport",
  景点: "bg-cat-sight",
  餐饮: "bg-cat-food",
  住宿: "bg-cat-hotel",
  自由活动: "bg-cat-free",
};

export function CategoryTag({ category }: { category: ActivityCategory }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-medium",
        catCls[category],
      )}
    >
      <i className={clsx("h-1.5 w-1.5 rounded-full", CATEGORY_DOT[category])} />
      {category}
    </span>
  );
}
