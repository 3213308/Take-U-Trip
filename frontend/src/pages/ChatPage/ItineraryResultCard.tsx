import { useNavigate } from "react-router-dom";
import type { Itinerary } from "@/types/itinerary";
import { fmtMoney } from "@/lib/utils/cost";
import { Badge } from "@/components/ui/Badge";

export function ItineraryResultCard({ itinerary }: { itinerary: Itinerary }) {
  const navigate = useNavigate();

  return (
    <div className="mt-4 overflow-hidden rounded-xl border border-brand-100 bg-brand-50/60">
      <div className="flex items-center justify-between border-b border-brand-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">📍</span>
          <div>
            <div className="text-sm font-semibold text-slate-800">
              {itinerary.destination} · {itinerary.days} 天行程
            </div>
            <div className="text-xs text-slate-400">
              预算 {fmtMoney(itinerary.total_budget)}
              {itinerary.warnings.length > 0 && ` · ${itinerary.warnings.length} 条提醒`}
            </div>
          </div>
        </div>
        {itinerary.warnings.length > 0 && <Badge tone="orange">有提醒</Badge>}
      </div>
      <div className="flex gap-2 px-4 py-3">
        <button
          className="flex-1 cursor-pointer rounded-lg bg-brand-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-brand-700"
          onClick={() => navigate("/itinerary")}
        >
          📋 查看行程清单
        </button>
        <button
          className="flex-1 cursor-pointer rounded-lg border border-brand-200 bg-white px-3 py-2 text-xs font-medium text-brand-700 transition-colors hover:bg-brand-100"
          onClick={() => navigate("/map")}
        >
          🗺️ 在地图查看
        </button>
      </div>
    </div>
  );
}
