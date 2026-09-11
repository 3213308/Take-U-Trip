import { useState } from "react";
import { useWishlistStore } from "@/stores/wishlistStore";
import { WishCard } from "./WishCard";
import { AddWishForm } from "./AddWishForm";
import { ImportFromItineraryDialog } from "./ImportFromItineraryDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export function WishlistPage() {
  const items = useWishlistStore((s) => s.items);
  const hydrated = useWishlistStore((s) => s.hydrated);
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

  const [filter, setFilter] = useState<"all" | "todo" | "done">("all");

  if (!hydrated) {
    return <div className="p-8 text-sm text-slate-300">加载中…</div>;
  }

  const visible = items.filter((i) =>
    filter === "all" ? true : filter === "done" ? i.completed : !i.completed,
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-8 py-8">
        <header className="flex items-end justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-800">愿望清单</h1>
            <p className="mt-1 text-sm text-slate-400">
              这次旅行想去的地方，去过的记得打卡
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => setImportOpen(true)}>
              📥 从行程导入
            </Button>
            <Button size="sm" onClick={() => setAddOpen(true)}>
              ＋ 手动添加
            </Button>
          </div>
        </header>

        {items.length === 0 ? (
          <EmptyState
            icon="⭐"
            title="清单还是空的"
            description="可以从已生成的行程中导入景点，或手动添加你想打卡的地方"
          />
        ) : (
          <>
            <div className="mt-5 flex gap-1.5">
              {(
                [
                  ["all", "全部"],
                  ["todo", "待打卡"],
                  ["done", "已打卡"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setFilter(key)}
                  className={
                    filter === key
                      ? "cursor-pointer rounded-full bg-brand-600 px-3.5 py-1.5 text-xs font-medium text-white"
                      : "cursor-pointer rounded-full bg-white px-3.5 py-1.5 text-xs text-slate-500 hover:bg-slate-50"
                  }
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {visible.map((item) => (
                <WishCard key={item.id} item={item} />
              ))}
            </div>
          </>
        )}

        <AddWishForm open={addOpen} onClose={() => setAddOpen(false)} />
        <ImportFromItineraryDialog
          open={importOpen}
          onClose={() => setImportOpen(false)}
        />
      </div>
    </div>
  );
}
