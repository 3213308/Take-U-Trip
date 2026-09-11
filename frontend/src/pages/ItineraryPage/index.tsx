import { useNavigate } from "react-router-dom";
import { useItineraryStore } from "@/stores/itineraryStore";
import { DaySection } from "./DaySection";
import { BudgetSummary } from "./BudgetSummary";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export function ItineraryPage() {
  const itinerary = useItineraryStore((s) => s.itinerary);
  const hydrated = useItineraryStore((s) => s.hydrated);
  const navigate = useNavigate();

  if (!hydrated) {
    return <div className="p-8 text-sm text-slate-300">加载中…</div>;
  }

  if (!itinerary || itinerary.days_plan.length === 0) {
    return (
      <div className="h-full">
        <EmptyState
          icon="📋"
          title="还没有行程"
          description="去和 Agent 聊聊你的旅行计划，生成后这里会自动出现一份可编辑的日程清单"
          action={
            <Button onClick={() => navigate("/chat")}>去生成行程</Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-6xl gap-6 px-8 py-8">
        {/* 左：日程时间线 */}
        <div className="min-w-0 flex-1 space-y-6">
          <header className="flex items-end justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-800">
                {itinerary.destination} · {itinerary.days} 天行程
              </h1>
              <p className="mt-1 text-sm text-slate-400">
                所有修改自动保存，点击活动可编辑
              </p>
            </div>
          </header>

          {itinerary.days_plan.map((day, di) => (
            <div key={`${day.date}-${di}`}>
              {di > 0 && (
                <div className="my-3 flex justify-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => useItineraryStore.getState().insertDay(di)}
                  >
                    ＋ 在此处插入新的一天
                  </Button>
                </div>
              )}
              <DaySection dayIndex={di} />
            </div>
          ))}
        </div>

        {/* 右：预算汇总 */}
        <div className="hidden w-72 shrink-0 lg:block">
          <div className="sticky top-8">
            <BudgetSummary />
          </div>
        </div>
      </div>
    </div>
  );
}
