import { useMemo, useState } from "react";
import type { Activity, DayPlan, Itinerary } from "@/types/itinerary";
import { useMapStore } from "@/stores/mapStore";
import { fmtMoney } from "@/lib/utils/cost";
import { clsx } from "clsx";
import { CATEGORY_DOT } from "@/components/ui/CategoryTag";

interface Props {
  itinerary: Itinerary;
  dayIndex: number;
  day: DayPlan;
  focusActivity: (index: number) => boolean;
  missLocations: string[];
}

export function TripPanel({ itinerary, dayIndex, day, focusActivity, missLocations }: Props) {
  const collapsed = useMapStore((s) => s.panelCollapsed);
  const setCollapsed = useMapStore((s) => s.setPanelCollapsed);
  const setDay = useMapStore((s) => s.setDay);
  const selectedOrigIdx = useMapStore((s) => s.selectedActivityOrigIdx);
  const setSelected = useMapStore((s) => s.setSelectedActivity);
  const [showMiss, setShowMiss] = useState(false);

  const sorted = useMemo(
    () =>
      day.activities
        .map((a, origIdx) => ({ a, origIdx }))
        .sort((x, y) => x.a.time.localeCompare(y.a.time)),
    [day.activities],
  );

  // 默认选中第一个活动
  const effectiveOrigIdx =
    selectedOrigIdx >= 0 && selectedOrigIdx < day.activities.length
      ? selectedOrigIdx
      : sorted[0]?.origIdx ?? -1;
  const selectedEntry = sorted.find((e) => e.origIdx === effectiveOrigIdx) ?? null;
  const selectedAct = selectedEntry?.a ?? null;

  const tryFocus = (origIdx: number, location?: string) => {
    setSelected(origIdx);
    if (location && missLocations.includes(location)) {
      alert("该地点未能在地图上定位，无法导航");
      return;
    }
    const ok = focusActivity(origIdx);
    if (!ok) {
      alert("该地点未能在当前地图上定位，暂时无法跳转");
    }
  };

  // ===== 收起态：胶囊浮标 =====
  if (collapsed) {
    return (
      <button
        className="absolute left-4 top-4 z-10 flex cursor-pointer items-center gap-3 rounded-full border border-slate-100 bg-white/95 py-2 pl-3 pr-4 shadow-lg backdrop-blur transition-transform hover:scale-[1.02]"
        onClick={() => setCollapsed(false)}
        title="展开行程面板"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">
          {dayIndex + 1}
        </span>
        <span className="text-xs text-slate-400">行程 · 第 {dayIndex + 1} 天</span>
        {selectedAct && (
          <>
            <span className="h-3 w-px bg-slate-200" />
            <span className="max-w-48 truncate text-sm font-medium text-slate-700">
              {selectedAct.name}
            </span>
            <span className="text-xs text-brand-600">{selectedAct.time}</span>
          </>
        )}
        <span className="text-slate-300">▸</span>
      </button>
    );
  }

  // ===== 展开态：完整卡片 =====
  return (
    <div className="absolute left-4 top-4 z-10 flex max-h-[calc(100%-2rem)] w-[360px] flex-col overflow-hidden rounded-2xl border border-slate-100 bg-white/95 shadow-xl backdrop-blur">
      {/* 行程头 */}
      <div className="flex items-center justify-between border-b border-slate-100 bg-gradient-to-r from-brand-600 to-brand-500 px-4 py-3 text-white">
        <div className="min-w-0">
          <div className="truncate text-sm font-bold">
            📍 {itinerary.destination} · {itinerary.days} 天
          </div>
          <div className="text-xs opacity-80">预算 {fmtMoney(itinerary.total_budget)}</div>
        </div>
        <button
          className="cursor-pointer rounded-lg px-2 py-1 text-xs text-white/80 transition-colors hover:bg-white/20"
          onClick={() => setCollapsed(true)}
          title="收起面板"
        >
          收起 ◂
        </button>
      </div>

      {/* 当前活动详情 */}
      {selectedAct && selectedEntry && (
        <div className="mx-4 mt-3 rounded-xl border border-brand-100 bg-brand-50/80 p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-brand-600">
            <span className="inline-block h-2 w-2 rounded-full bg-brand-500" />
            当前活动
          </div>
          <div className="mt-1 text-sm font-semibold text-slate-800">
            {selectedAct.time} · {selectedAct.name}
          </div>
          {selectedAct.location && (
            <div className="mt-0.5 text-xs text-slate-500">📍 {selectedAct.location}</div>
          )}
          {selectedAct.notes && (
            <div className="mt-0.5 text-xs text-slate-400">💡 {selectedAct.notes}</div>
          )}
          {selectedAct.cost > 0 && (
            <div className="mt-0.5 text-xs text-teal-600">💰 {fmtMoney(selectedAct.cost)}</div>
          )}
          <button
            className="mt-2 w-full cursor-pointer rounded-lg bg-brand-600 py-1.5 text-xs font-medium text-white transition-colors hover:bg-brand-700"
            onClick={() => tryFocus(selectedEntry.origIdx, selectedAct.location)}
          >
            🧭 在地图上定位
          </button>
        </div>
      )}

      {/* 天切换 */}
      <div className="mt-3 flex gap-1 overflow-x-auto px-4 pb-1">
        {itinerary.days_plan.map((d, i) => (
          <button
            key={`${d.date}-${i}`}
            className={clsx(
              "shrink-0 cursor-pointer rounded-full px-3 py-1 text-xs font-medium transition-colors",
              i === dayIndex
                ? "bg-slate-800 text-white"
                : "bg-slate-100 text-slate-500 hover:bg-slate-200",
            )}
            onClick={() => setDay(i)}
          >
            第{i + 1}天
          </button>
        ))}
      </div>

      {/* 活动列表 */}
      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        <div className="mb-1 px-2 text-[11px] text-slate-400">
          {itinerary.days_plan[dayIndex]?.date} {itinerary.days_plan[dayIndex]?.theme && `· ${itinerary.days_plan[dayIndex].theme}`}
        </div>
        {sorted.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-slate-300">当天没有活动</p>
        ) : (
          <ul className="space-y-0.5">
            {sorted.map(({ a, origIdx }) => {
              const isActive = origIdx === effectiveOrigIdx;
              return (
                <li key={`${a.time}-${a.name}-${origIdx}`}>
                  <button
                    className={clsx(
                      "flex w-full cursor-pointer items-center gap-2.5 rounded-xl px-2 py-2 text-left transition-colors",
                      isActive
                        ? "bg-brand-50 ring-1 ring-brand-200"
                        : "hover:bg-slate-50",
                    )}
                    onClick={() => tryFocus(origIdx, a.location)}
                    title="定位到地图"
                  >
                    <i
                      className={clsx(
                        "h-2 w-2 shrink-0 rounded-full",
                        CATEGORY_DOT[a.category],
                      )}
                    />
                    <span className="w-20 shrink-0 text-[11px] font-medium text-slate-400">
                      {a.time}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span
                        className={clsx(
                          "block truncate text-xs",
                          isActive ? "font-semibold text-brand-700" : "font-medium text-slate-700",
                        )}
                      >
                        {a.name}
                      </span>
                      {a.location && (
                        <span className="block truncate text-[11px] text-slate-400">
                          {a.location}
                          {a.cost > 0 && ` · ${fmtMoney(a.cost)}`}
                        </span>
                      )}
                    </span>
                    {isActive && <span className="shrink-0 text-xs">🧭</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* 未定位提示 */}
      {missLocations.length > 0 && (
        <div className="border-t border-slate-100 px-3 py-2">
          <button
            className="flex w-full cursor-pointer items-center justify-between text-[11px] text-amber-600"
            onClick={() => setShowMiss(!showMiss)}
          >
            <span>⚠ {missLocations.length} 个地点未能定位</span>
            <span>{showMiss ? "▲" : "▼"}</span>
          </button>
          {showMiss && (
            <ul className="mt-1.5 space-y-0.5 px-1">
              {missLocations.map((m, i) => (
                <li key={i} className="truncate text-[11px] text-slate-400">
                  · {m}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
