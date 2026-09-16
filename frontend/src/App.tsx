import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./components/layout/Sidebar";
import { bindAllStores } from "./storage";
import { loadAMap } from "./lib/map/loader";

export default function App() {
  useEffect(() => {
    const unbind = bindAllStores();
    // 预热：应用启动后闲时就把高德 JS API 拉到缓存里，
    // 等用户真的进入"地图导航"时无需再冷加载，首屏明显变快。
    const warm = () => {
      loadAMap().catch(() => {});
    };
    if ("requestIdleCallback" in window) {
      const id = requestIdleCallback(warm, { timeout: 3000 });
      return () => {
        cancelIdleCallback(id);
        unbind();
      };
    }
    const t = setTimeout(warm, 1500);
    return () => {
      clearTimeout(t);
      unbind();
    };
  }, []);

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
