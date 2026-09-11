import { useEffect, useMemo, useState } from "react";
import { useWishlistStore } from "@/stores/wishlistStore";
import { useItineraryStore } from "@/stores/itineraryStore";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { clsx } from "clsx";

interface Candidate {
  name: string;
  location: string;
  city: string;
}

export function ImportFromItineraryDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const itinerary = useItineraryStore((s) => s.itinerary);
  const items = useWishlistStore((s) => s.items);
  const importMany = useWishlistStore((s) => s.importMany);

  const [selected, setSelected] = useState<Set<string>>(new Set());

  const candidates = useMemo<Candidate[]>(() => {
    if (!itinerary) return [];
    const seen = new Set<string>();
    const result: Candidate[] = [];
    for (const d of itinerary.days_plan) {
      for (const a of d.activities) {
        if (a.category !== "景点" || !a.name) continue;
        const key = `${a.name}::${itinerary.destination}`;
        if (seen.has(key)) continue;
        seen.add(key);
        result.push({ name: a.name, location: a.location, city: itinerary.destination });
      }
    }
    return result;
  }, [itinerary]);

  const existingKeys = useMemo(
    () => new Set(items.map((i) => `${i.name}::${i.city}`)),
    [items],
  );

  useEffect(() => {
    if (open) {
      setSelected(
        new Set(
          candidates
            .filter((c) => !existingKeys.has(`${c.name}::${c.city}`))
            .map((c) => `${c.name}::${c.city}`),
        ),
      );
    }
  }, [open, candidates, existingKeys]);

  const newCount = candidates.filter(
    (c) => !existingKeys.has(`${c.name}::${c.city}`),
  ).length;
  const existingCount = candidates.length - newCount;

  const toggle = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const confirm = () => {
    const chosen = candidates.filter((c) => selected.has(`${c.name}::${c.city}`));
    if (chosen.length) {
      importMany(chosen.map((c) => ({ ...c, source: "itinerary" as const })));
    }
    onClose();
  };

  if (!itinerary) {
    return (
      <Modal open={open} title="从行程导入" onClose={onClose} width="max-w-md">
        <p className="py-4 text-center text-sm text-slate-400">
          还没有生成行程，先去和 Agent 聊聊吧
        </p>
      </Modal>
    );
  }

  return (
    <Modal open={open} title="从行程导入景点" onClose={onClose} width="max-w-md">
      {candidates.length === 0 ? (
        <p className="py-4 text-center text-sm text-slate-400">
          当前行程中没有景点类活动
        </p>
      ) : (
        <>
          <p className="mb-3 text-xs text-slate-400">
            将导入 {selected.size} 项{existingCount > 0 && ` · 已存在 ${existingCount} 项（自动跳过）`}
          </p>
          <ul className="max-h-72 space-y-1.5 overflow-y-auto">
            {candidates.map((c) => {
              const key = `${c.name}::${c.city}`;
              const exists = existingKeys.has(key);
              const checked = !exists && selected.has(key);
              return (
                <li key={key}>
                  <label
                    className={clsx(
                      "flex items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors",
                      exists
                        ? "border-slate-100 bg-slate-50 opacity-60"
                        : checked
                          ? "cursor-pointer border-brand-200 bg-brand-50/60"
                          : "cursor-pointer border-slate-100 hover:bg-slate-50",
                    )}
                  >
                    <input
                      type="checkbox"
                      className="accent-brand-600"
                      disabled={exists}
                      checked={checked}
                      onChange={() => toggle(key)}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-slate-700">
                        {c.name}
                      </div>
                      <div className="truncate text-xs text-slate-400">
                        📍 {c.location || c.city}
                      </div>
                    </div>
                    {exists && <span className="shrink-0 text-xs text-slate-400">已存在</span>}
                  </label>
                </li>
              );
            })}
          </ul>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={onClose}>
              取消
            </Button>
            <Button size="sm" disabled={selected.size === 0} onClick={confirm}>
              导入 {selected.size} 项
            </Button>
          </div>
        </>
      )}
    </Modal>
  );
}
