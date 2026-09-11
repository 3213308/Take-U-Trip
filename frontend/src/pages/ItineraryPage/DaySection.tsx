import { useState } from "react";
import { useItineraryStore } from "@/stores/itineraryStore";
import { createEmptyActivity } from "@/types/itinerary";
import { formatDateCN } from "@/lib/utils/date";
import { fmtMoney } from "@/lib/utils/cost";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ActivityRow } from "./ActivityRow";
import { ActivityEditForm, type ActivityFormState } from "./ActivityEditForm";

export function DaySection({ dayIndex }: { dayIndex: number }) {
  const day = useItineraryStore((s) => s.itinerary?.days_plan[dayIndex]);
  const updateDay = useItineraryStore((s) => s.updateDay);
  const removeDay = useItineraryStore((s) => s.removeDay);
  const addActivity = useItineraryStore((s) => s.addActivity);

  const [editingTheme, setEditingTheme] = useState(false);
  const [themeDraft, setThemeDraft] = useState("");
  const [editingDate, setEditingDate] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  if (!day) return null;

  const openAdd = () => {
    setEditingIndex(null);
    setFormOpen(true);
  };

  const openEdit = (ai: number) => {
    setEditingIndex(ai);
    setFormOpen(true);
  };

  const onSubmit = (form: ActivityFormState) => {
    if (editingIndex === null) {
      addActivity(dayIndex, { ...form, cost: Number(form.cost) || 0 });
    } else {
      useItineraryStore
        .getState()
        .updateActivity(dayIndex, editingIndex, { ...form, cost: Number(form.cost) || 0 });
    }
    setFormOpen(false);
  };

  const initialForm = (): ActivityFormState => {
    const a =
      editingIndex !== null ? day.activities[editingIndex] : createEmptyActivity();
    return {
      time: a.time,
      name: a.name,
      location: a.location,
      category: a.category,
      cost: String(a.cost),
      notes: a.notes,
    };
  };

  const activities = day.activities
    .map((a, origIdx) => ({ a, origIdx }))
    .sort((x, y) => x.a.time.localeCompare(y.a.time));

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm">
      {/* 天头部 */}
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/60 px-5 py-3.5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-xl bg-brand-600 text-white">
            <span className="text-[10px] leading-none opacity-80">Day</span>
            <span className="text-sm font-bold leading-tight">{dayIndex + 1}</span>
          </div>
          <div className="min-w-0">
            {editingDate ? (
              <input
                autoFocus
                type="date"
                value={day.date}
                onChange={(e) => updateDay(dayIndex, { date: e.target.value })}
                onBlur={() => setEditingDate(false)}
                className="w-36 rounded-md border border-brand-300 bg-white px-2 py-0.5 text-xs text-slate-700 outline-none"
              />
            ) : (
              <button
                className="flex cursor-pointer items-center gap-1.5 text-sm font-semibold text-slate-800 hover:text-brand-600"
                title="点击修改日期"
                onClick={() => setEditingDate(true)}
              >
                {formatDateCN(day.date)}
                <span className="text-[10px] text-slate-300">✎</span>
              </button>
            )}
            {editingTheme ? (
              <input
                autoFocus
                value={themeDraft}
                onChange={(e) => setThemeDraft(e.target.value)}
                onBlur={() => {
                  if (themeDraft.trim() !== day.theme) {
                    updateDay(dayIndex, { theme: themeDraft.trim() });
                  }
                  setEditingTheme(false);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
                className="mt-0.5 w-full max-w-40 rounded-md border border-brand-300 bg-white px-2 py-0.5 text-xs text-slate-700 outline-none"
                placeholder="当日主题"
              />
            ) : (
              <button
                className="mt-0.5 flex max-w-full cursor-pointer items-center gap-1 truncate text-xs text-slate-400 hover:text-brand-600"
                title="点击修改主题"
                onClick={() => {
                  setThemeDraft(day.theme);
                  setEditingTheme(true);
                }}
              >
                {day.theme || "点击添加当日主题"}
                <span className="text-[10px]">✎</span>
              </button>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span className="text-xs text-slate-400">
            {day.activities.length} 项 · {fmtMoney(day.daily_budget)}
          </span>
          <Button variant="secondary" size="sm" onClick={openAdd}>
            ＋ 添加活动
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-slate-300 hover:text-red-500"
            onClick={() => setConfirmDelete(true)}
          >
            🗑
          </Button>
        </div>
      </div>

      {/* 活动列表 */}
      {activities.length === 0 ? (
        <div className="px-5 py-8 text-center text-sm text-slate-300">
          这一天还没有安排，点击右上角添加活动
        </div>
      ) : (
        <ul className="divide-y divide-slate-50">
          {activities.map(({ a, origIdx }) => (
            <ActivityRow
              key={`${a.time}-${a.name}-${origIdx}`}
              dayIndex={dayIndex}
              activityIndex={origIdx}
              onEdit={() => openEdit(origIdx)}
            />
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title="删除这一天？"
        message={`将删除第 ${dayIndex + 1} 天（${formatDateCN(day.date)}）及其全部 ${day.activities.length} 项活动，此操作不可撤销。`}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => {
          removeDay(dayIndex);
          setConfirmDelete(false);
        }}
      />

      <ActivityEditForm
        open={formOpen}
        title={editingIndex === null ? "添加活动" : "编辑活动"}
        initial={initialForm()}
        onClose={() => setFormOpen(false)}
        onSubmit={onSubmit}
      />
    </section>
  );
}
