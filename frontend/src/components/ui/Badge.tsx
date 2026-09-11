import { clsx } from "clsx";
import type { ReactNode } from "react";

const tones = {
  gray: "bg-slate-100 text-slate-600",
  green: "bg-emerald-100 text-emerald-700",
  blue: "bg-blue-100 text-blue-700",
  orange: "bg-amber-100 text-amber-700",
  red: "bg-red-100 text-red-700",
  brand: "bg-brand-100 text-brand-700",
} as const;

export function Badge({
  tone = "gray",
  children,
  className,
}: {
  tone?: keyof typeof tones;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
