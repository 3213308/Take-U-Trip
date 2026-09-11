import { clsx } from "clsx";

export function ProgressBar({
  ratio,
  className,
  barClassName,
}: {
  /** 0~1，超 1 截断显示为满 */
  ratio: number;
  className?: string;
  barClassName?: string;
}) {
  const clamped = Math.max(0, Math.min(1, ratio));
  return (
    <div className={clsx("h-2 w-full overflow-hidden rounded-full bg-slate-100", className)}>
      <div
        className={clsx("h-full rounded-full transition-all", barClassName ?? "bg-brand-500")}
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  );
}
