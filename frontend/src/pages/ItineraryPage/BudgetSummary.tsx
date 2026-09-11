import { useItineraryStore } from "@/stores/itineraryStore";
import { costsByCategory, fmtMoney, sumActivitiesCost } from "@/lib/utils/cost";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { clsx } from "clsx";
import type { ActivityCategory } from "@/types/itinerary";

const CATEGORY_LABELS: Record<ActivityCategory, string> = {
  交通: "交通",
  景点: "景点门票",
  餐饮: "餐饮",
  住宿: "住宿",
  自由活动: "自由活动",
};

export function BudgetSummary() {
  const itinerary = useItineraryStore((s) => s.itinerary);
  if (!itinerary) return null;

  const planned = sumActivitiesCost(itinerary);
  const total = itinerary.total_budget;
  const ratio = total > 0 ? planned / total : 0;
  const over = planned > total && total > 0;
  const byCat = costsByCategory(itinerary);

  return (
    <aside className="space-y-5 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div>
        <h3 className="text-sm font-semibold text-slate-700">预算概览</h3>
        <div className="mt-3 flex items-baseline justify-between">
          <span className="text-xs text-slate-400">活动费用合计</span>
          <span className={clsx("text-lg font-bold", over ? "text-red-500" : "text-slate-800")}>
            {fmtMoney(planned)}
          </span>
        </div>
        <div className="mt-1 flex items-baseline justify-between">
          <span className="text-xs text-slate-400">总预算</span>
          <span className="text-sm text-slate-500">{fmtMoney(total)}</span>
        </div>
        <ProgressBar
          className="mt-2"
          ratio={ratio}
          barClassName={over ? "bg-red-400" : "bg-brand-500"}
        />
        <p className={clsx("mt-1.5 text-xs", over ? "text-red-500" : "text-slate-400")}>
          {over
            ? `已超预算 ${fmtMoney(planned - total)}`
            : total > 0
              ? `剩余 ${fmtMoney(total - planned)}（${Math.round(ratio * 100)}%）`
              : "未设置总预算"}
        </p>
      </div>

      <div>
        <h4 className="mb-2 text-xs font-medium text-slate-400">分类小计</h4>
        <div className="space-y-1.5">
          {(Object.keys(CATEGORY_LABELS) as ActivityCategory[]).map((cat) => (
            <div key={cat} className="flex items-center justify-between text-xs">
              <span className="text-slate-500">{CATEGORY_LABELS[cat]}</span>
              <span className="font-medium text-slate-700">{fmtMoney(byCat[cat])}</span>
            </div>
          ))}
        </div>
      </div>

      {itinerary.transport_suggestions.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-medium text-slate-400">交通建议</h4>
          <ul className="space-y-1 text-xs text-slate-500">
            {itinerary.transport_suggestions.map((t, i) => (
              <li key={i} className="leading-relaxed">
                · {t}
              </li>
            ))}
          </ul>
        </div>
      )}

      {itinerary.warnings.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-medium text-slate-400">提醒</h4>
          <ul className="space-y-1 text-xs text-amber-600">
            {itinerary.warnings.map((w, i) => (
              <li key={i} className="leading-relaxed">
                ⚠ {w}
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
