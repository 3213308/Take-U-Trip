import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./components/layout/Sidebar";
import { bindAllStores } from "./storage";

export default function App() {
  useEffect(() => {
    const unbind = bindAllStores();
    return unbind;
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
