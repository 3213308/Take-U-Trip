import type { WishStats } from "@/stores/wishlistStore";
import { ProgressBar } from "@/components/ui/ProgressBar";

export function ProgressStats({ stats }: { stats: WishStats }) {
  const ratio = stats.total > 0 ? stats.completed / stats.total : 0;

  return (
    <div className="mt-6 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-slate-800">{stats.completed}</span>
          <span className="text-sm text-slate-400">/ {stats.total} 已打卡</span>
        </div>
        <span className="text-sm font-medium text-brand-600">
          {Math.round(ratio * 100)}%
        </span>
      </div>
      <ProgressBar className="mt-3" ratio={ratio} />
    </div>
  );
}
