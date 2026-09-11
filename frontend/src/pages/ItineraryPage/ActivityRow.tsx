import { useState } from "react";
import { useItineraryStore } from "@/stores/itineraryStore";
import { useWishlistStore } from "@/stores/wishlistStore";
import { fmtMoney } from "@/lib/utils/cost";
import { CategoryTag } from "@/components/ui/CategoryTag";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

export function ActivityRow({
  dayIndex,
  activityIndex,
  onEdit,
}: {
  dayIndex: number;
  activityIndex: number;
  onEdit: () => void;
}) {
  const itinerary = useItineraryStore((s) => s.itinerary);
  const removeActivity = useItineraryStore((s) => s.removeActivity);
  const moveActivity = useItineraryStore((s) => s.moveActivity);
  const addWish = useWishlistStore((s) => s.add);

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [wishAdded, setWishAdded] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const day = itinerary?.days_plan[dayIndex];
  const activity = day?.activities[activityIndex];
  if (!day || !activity) return null;

  const total = day.activities.length;

  const addToWishlist = () => {
    addWish({
      name: activity.name,
      location: activity.location,
      city: itinerary?.destination ?? "",
      source: "itinerary",
      notes: activity.notes,
    });
    setWishAdded(true);
    setTimeout(() => setWishAdded(false), 1500);
  };

  return (
    <li
      className="group flex items-start gap-4 px-5 py-3 transition-colors hover:bg-slate-50/70 cursor-pointer"
      onClick={() => setExpanded(!expanded)}
    >
      {/* 时间徽章 */}
      <div className="w-24 shrink-0 rounded-lg bg-slate-100 px-2 py-1.5 text-center text-xs font-medium text-slate-600">
        {activity.time}
      </div>

      {/* 主信息 */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-slate-800">
            {activity.name}
          </span>
          <CategoryTag category={activity.category} />
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
          {activity.location && <span>📍 {activity.location}</span>}
          {activity.cost > 0 && <span>{fmtMoney(activity.cost)}</span>}
        </div>
        {expanded && (
          <div className="mt-1.5 rounded-md bg-slate-50 px-2.5 py-1.5 text-xs leading-relaxed text-slate-500">
            {activity.notes || "无备注"}
          </div>
        )}
      </div>

      {/* 操作区 */}
      <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100" onClick={(e) => e.stopPropagation()}>
        {activity.category === "景点" && (
          <button
            className="cursor-pointer rounded-lg px-2 py-1.5 text-xs text-slate-400 hover:bg-amber-50 hover:text-amber-600"
            title="加入愿望清单"
            onClick={addToWishlist}
          >
            {wishAdded ? "✓已加" : "☆"}
          </button>
        )}
        <button
          className="cursor-pointer rounded-lg px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-30"
          title="上移"
          disabled={activityIndex === 0}
          onClick={() => moveActivity(dayIndex, activityIndex, activityIndex - 1)}
        >
          ↑
        </button>
        <button
          className="cursor-pointer rounded-lg px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-30"
          title="下移"
          disabled={activityIndex === total - 1}
          onClick={() => moveActivity(dayIndex, activityIndex, activityIndex + 1)}
        >
          ↓
        </button>
        <button
          className="cursor-pointer rounded-lg px-2 py-1.5 text-xs text-slate-400 hover:bg-brand-50 hover:text-brand-600"
          title="编辑"
          onClick={onEdit}
        >
          ✎
        </button>
        <button
          className="cursor-pointer rounded-lg px-2 py-1.5 text-xs text-slate-400 hover:bg-red-50 hover:text-red-500"
          title="删除"
          onClick={() => setConfirmDelete(true)}
        >
          🗑
        </button>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="删除这项活动？"
        message={`将删除「${activity.name}」（${activity.time}）。`}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => {
          removeActivity(dayIndex, activityIndex);
          setConfirmDelete(false);
        }}
      />
    </li>
  );
}
