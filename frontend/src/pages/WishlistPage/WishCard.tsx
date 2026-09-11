import { useState } from "react";
import type { WishItem } from "@/types/wishlist";
import { useWishlistStore } from "@/stores/wishlistStore";
import { clsx } from "clsx";
import { Badge } from "@/components/ui/Badge";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

export function WishCard({ item }: { item: WishItem }) {
  const toggle = useWishlistStore((s) => s.toggle);
  const remove = useWishlistStore((s) => s.remove);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const doneDate = item.completedAt
    ? (() => {
        const d = new Date(item.completedAt);
        return `${d.getMonth() + 1}.${d.getDate()}`;
      })()
    : "";

  return (
    <div
      className={clsx(
        "group relative flex cursor-pointer flex-col gap-2 rounded-2xl border p-4 transition-all",
        item.completed
          ? "border-emerald-100 bg-emerald-50/50"
          : "border-slate-100 bg-white shadow-sm hover:border-brand-200 hover:shadow-md",
      )}
      onClick={() => toggle(item.id)}
    >
      {/* 打卡勾选框 */}
      <div className="flex items-start justify-between">
        <div
          className={clsx(
            "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
            item.completed
              ? "border-emerald-500 bg-emerald-500 text-white"
              : "border-slate-200 bg-white text-transparent group-hover:border-brand-400",
          )}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
            <path d="M20 6 9 17l-5-5" />
          </svg>
        </div>
        <button
          className="cursor-pointer rounded-lg px-1.5 py-0.5 text-xs text-slate-300 opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100"
          title="删除"
          onClick={(e) => {
            e.stopPropagation();
            setConfirmDelete(true);
          }}
        >
          🗑
        </button>
      </div>

      <div>
        <h3
          className={clsx(
            "text-sm font-semibold",
            item.completed ? "text-slate-400 line-through" : "text-slate-800",
          )}
        >
          {item.name}
        </h3>
        {item.location && (
          <p className="mt-1 text-xs text-slate-400">📍 {item.location}</p>
        )}
        {item.notes && <p className="mt-1 text-xs text-slate-400">{item.notes}</p>}
      </div>

      <div className="flex items-center gap-1.5">
        <Badge tone={item.source === "itinerary" ? "brand" : "gray"}>
          {item.source === "itinerary" ? "来自行程" : "手动添加"}
        </Badge>
        {item.completed && doneDate && <Badge tone="green">✓ {doneDate} 打卡</Badge>}
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="移出愿望清单？"
        message={`将删除「${item.name}」这条打卡心愿。`}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => {
          remove(item.id);
          setConfirmDelete(false);
        }}
      />
    </div>
  );
}
