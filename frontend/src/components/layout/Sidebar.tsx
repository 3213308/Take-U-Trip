import { NavLink } from "react-router-dom";
import { clsx } from "clsx";
import { useEffect, useState } from "react";
import { checkHealth } from "@/api/chat";

const navItems = [
  { to: "/chat", label: "智能规划", icon: "💬" },
  { to: "/map", label: "地图导航", icon: "🗺️" },
  { to: "/itinerary", label: "行程清单", icon: "📋" },
  { to: "/wishlist", label: "愿望清单", icon: "⭐" },
];

type HealthState = "checking" | "ok" | "down";

export function Sidebar() {
  const [health, setHealth] = useState<HealthState>("checking");

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      const ok = await checkHealth();
      if (!cancelled) setHealth(ok ? "ok" : "down");
    };
    probe();
    const timer = setInterval(probe, 30_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-lg text-white shadow-sm">
          ✈️
        </div>
        <div>
          <div className="text-sm font-bold tracking-wide text-slate-800">
            Take-U-Trip
          </div>
          <div className="text-[11px] text-slate-400">智能旅游规划助手</div>
        </div>
      </div>

      <nav className="mt-2 flex flex-1 flex-col gap-1 px-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-700",
              )
            }
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-slate-100 px-5 py-4">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span
            className={clsx(
              "h-2 w-2 rounded-full",
              health === "ok" && "bg-emerald-500",
              health === "down" && "bg-red-500",
              health === "checking" && "bg-slate-300 animate-pulse",
            )}
          />
          {health === "ok" && "Agent 服务正常"}
          {health === "down" && "Agent 服务离线"}
          {health === "checking" && "检测服务中…"}
        </div>
      </div>
    </aside>
  );
}
