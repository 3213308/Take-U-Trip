import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import type { Activity } from "@/types/itinerary";
import { loadAMap } from "@/lib/map/loader";
import { batchGeocode, extractCity } from "@/lib/map/geocode";
import { useMapStore, type GeoPoint } from "@/stores/mapStore";
import { fmtMoney } from "@/lib/utils/cost";

export interface MapCanvasHandle {
  /** 定位到指定活动，返回是否成功（点位缺失时失败） */
  focusActivity: (index: number) => boolean;
}

interface Props {
  activities: Activity[];
  destination: string;
  onMissChange: (miss: string[]) => void;
}

const CATEGORY_COLOR_HEX: Record<string, string> = {
  交通: "#3b82f6",
  景点: "#10b981",
  餐饮: "#f59e0b",
  住宿: "#8b5cf6",
  自由活动: "#94a3b8",
};

export const MapCanvas = forwardRef<MapCanvasHandle, Props>(
  function MapCanvas({ activities, destination, onMissChange }, ref) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [AMap, setAMap] = useState<any>(null);
    const [map, setMap] = useState<any>(null);
    const [error, setError] = useState("");
    // 高德底图瓦片是否加载完成；完成前显示加载遮罩，避免灰底上飘着孤立点
    const [tilesReady, setTilesReady] = useState(false);

    const overlaysRef = useRef<{ markers: (any | null)[]; polylines: any[] }>({
      markers: [],
      polylines: [],
    });
    const infoWindowRef = useRef<any>(null);
    const pointsRef = useRef<(GeoPoint | null)[]>([]);
    const activitiesRef = useRef<Activity[]>([]);
    const openInfoWindowRef = useRef<(index: number) => void>(() => {});
    const getGeocode = useMapStore((s) => s.getGeocode);
    const putGeocode = useMapStore((s) => s.putGeocode);

    // 初始化地图
    useEffect(() => {
      let cancelled = false;
      let mapInstance: any = null;

      loadAMap()
        .then((amap) => {
          if (cancelled || !containerRef.current) return;
          mapInstance = new amap.Map(containerRef.current, {
            zoom: 12,
            viewMode: "2D",
          });
          mapInstance.addControl(new amap.Scale());
          mapInstance.addControl(new amap.ToolBar({ position: "RB" }));
          mapInstance.on("complete", () => setTilesReady(true));
          infoWindowRef.current = new amap.InfoWindow({ offset: new amap.Pixel(0, -32) });
          setAMap(amap);
          setMap(mapInstance);
        })
        .catch((e) => {
          if (!cancelled) setError(e instanceof Error ? e.message : String(e));
        });

      return () => {
        cancelled = true;
        if (mapInstance) {
          try {
            mapInstance.destroy();
          } catch {
            /* 已销毁 */
          }
        }
      };
    }, []);

    // 渲染当前天（activities 或地图就绪时）
    useEffect(() => {
      if (!AMap || !map) return;

      let cancelled = false;
      const { markers, polylines } = overlaysRef.current;

      const clearOverlays = () => {
        markers.forEach((m) => m?.remove());
        polylines.forEach((p) => p.remove());
        overlaysRef.current = { markers: [], polylines: [] };
        infoWindowRef.current?.close();
      };

      const render = async () => {
        clearOverlays();
        // 切换天时同步清空 pointsRef，避免旧天坐标被 focusActivity 读到
        pointsRef.current = [];
        if (!activities.length) {
          onMissChange([]);
          return;
        }

        // 1. 地理编码（自带经纬度优先，缓存次之，最后批量 geocode）
        const needGeocode: { index: number; location: string }[] = [];
        const resolved: (GeoPoint | null)[] = activities.map((a, i) => {
          // 后端工具直接返回了经纬度，跳过 geocode
          if (typeof a.lng === "number" && typeof a.lat === "number" && a.lng && a.lat) {
            return { lng: a.lng, lat: a.lat };
          }
          const loc = a.location?.trim();
          if (!loc) return null;
          const key = `${destination}::${loc}`;
          const cached = getGeocode(key);
          if (cached) return cached;
          needGeocode.push({ index: i, location: loc });
          return null;
        });

        // 先把同步已知的坐标写入 pointsRef（不等 geocode），保证自带坐标的活动立即可点
        const applyOffsets = (pts: (GeoPoint | null)[]): (GeoPoint | null)[] => {
          const dup = new Map<string, number>();
          for (const p of pts) {
            if (!p) continue;
            const k = `${p.lng.toFixed(4)},${p.lat.toFixed(4)}`;
            dup.set(k, (dup.get(k) ?? 0) + 1);
          }
          const seen = new Map<string, number>();
          return pts.map((p) => {
            if (!p) return null;
            const k = `${p.lng.toFixed(4)},${p.lat.toFixed(4)}`;
            const n = seen.get(k) ?? 0;
            seen.set(k, n + 1);
            if (n === 0 || (dup.get(k) ?? 1) <= 1) return p;
            const angle = (n / 8) * Math.PI * 2;
            const d = 0.0007 * (1 + Math.floor(n / 8));
            return { lng: p.lng + Math.cos(angle) * d, lat: p.lat + Math.sin(angle) * d };
          });
        };
        pointsRef.current = applyOffsets(resolved);

        if (needGeocode.length) {
          try {
            const results = await batchGeocode(
              AMap,
              [...new Set(needGeocode.map((n) => n.location))],
              extractCity(destination),
            );
            results.forEach((pt, addr) => {
              putGeocode(`${destination}::${addr}`, pt);
            });
            for (const n of needGeocode) {
              const key = `${destination}::${n.location}`;
              resolved[n.index] = getGeocode(key) ?? null;
            }
          } catch (e) {
            console.warn("[map] 地理编码失败", e);
          }
        }

        // 兜底：具体地点编码失败、或活动本身无地点（交通/自由活动）时，定位到目的地城市中心
        const stillMissing = resolved
          .map((p, i) => (p ? -1 : i))
          .filter((i): i is number => i >= 0);
        if (stillMissing.length) {
          const city = extractCity(destination) ?? destination;
          const destKey = `${destination}::__city__`;
          let cityPt: GeoPoint | null = getGeocode(destKey) ?? null;
          if (!cityPt) {
            const fallback = await batchGeocode(AMap, [city]);
            cityPt = fallback.get(city) ?? null;
            if (cityPt) putGeocode(destKey, cityPt);
          }
          if (cityPt) {
            for (const i of stillMissing) resolved[i] = cityPt;
          }
        }
        if (cancelled) return;

        // geocode 完成后重新计算偏移并更新 pointsRef
        pointsRef.current = applyOffsets(resolved);
        onMissChange(
          activities
            .filter((a, i) => a.location?.trim() && !resolved[i])
            .map((a) => a.location),
        );

        // 2. 打点（markers 数组用 null 占位，保证与 activities 索引一一对应）
        const content = (a: Activity) =>
          `<div style="min-width:180px;font-size:13px;">
            <div style="font-weight:600;color:#0f172a;">${a.name}</div>
            <div style="color:#64748b;margin-top:2px;">🕐 ${a.time}${a.location ? ` · 📍 ${a.location}` : ""}</div>
            ${a.cost > 0 ? `<div style="color:#0d9488;margin-top:2px;">${fmtMoney(a.cost)}</div>` : ""}
            ${a.notes ? `<div style="color:#94a3b8;margin-top:2px;font-size:12px;">${a.notes}</div>` : ""}
          </div>`;

        // 共享打开函数：marker 点击与面板"去这里"都走这里
        activitiesRef.current = activities;
        openInfoWindowRef.current = (index: number) => {
          const pt = pointsRef.current[index];
          const a = activitiesRef.current[index];
          if (!pt || !a) return;
          infoWindowRef.current?.setContent(content(a));
          infoWindowRef.current?.open(map, [pt.lng, pt.lat]);
        };

        let seq = 0;
        const newMarkers: (any | null)[] = [];
        // 用偏移后的坐标打点，与 InfoWindow/focusActivity 定位保持一致
        pointsRef.current.forEach((pt, i) => {
          if (!pt) {
            newMarkers.push(null);
            return;
          }
          seq++;
          const a = activities[i];
          const color = CATEGORY_COLOR_HEX[a.category] ?? "#94a3b8";
          const marker = new AMap.Marker({
            position: [pt.lng, pt.lat],
            title: a.name,
            content: `<div style="width:26px;height:26px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:${color};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;"><span style="transform:rotate(45deg);color:#fff;font-size:12px;font-weight:600;">${seq}</span></div>`,
          });
          marker.on("click", () => {
            openInfoWindowRef.current(i);
          });
          marker.setMap(map);
          newMarkers.push(marker);
        });

        // 3. 按顺序连线（虚线），跳过定位失败的点
        const withPoints = pointsRef.current
          .map((pt, i) => ({ pt, i }))
          .filter((x): x is { pt: GeoPoint; i: number } => Boolean(x.pt));
        const newPolylines: any[] = [];
        for (let k = 0; k < withPoints.length - 1; k++) {
          const line = new AMap.Polyline({
            path: [
              [withPoints[k].pt.lng, withPoints[k].pt.lat],
              [withPoints[k + 1].pt.lng, withPoints[k + 1].pt.lat],
            ],
            strokeColor: "#14b8a6",
            strokeWeight: 3,
            strokeStyle: "dashed",
            strokeOpacity: 0.8,
          });
          line.setMap(map);
          newPolylines.push(line);
        }

        overlaysRef.current = { markers: newMarkers, polylines: newPolylines };

        // 4. 自适应视野
        const fitTargets = newMarkers.filter(Boolean);
        if (fitTargets.length) {
          map.setFitView(fitTargets, false, [80, 80, 80, 420]);
        }
      };

      void render();
      return () => {
        cancelled = true;
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [AMap, map, activities, destination]);

    useImperativeHandle(ref, () => ({
      focusActivity: (index: number) => {
        if (!map) return false;
        const pt = pointsRef.current[index];
        if (!pt) return false;
        infoWindowRef.current?.close();
        map.setZoomAndCenter(16, [pt.lng, pt.lat], true);
        requestAnimationFrame(() => {
          openInfoWindowRef.current(index);
        });
        return true;
      },
    }), [map]);

    if (error) {
      return (
        <div className="flex h-full items-center justify-center p-8">
          <div className="max-w-md rounded-2xl border border-amber-200 bg-amber-50 p-6 text-center">
            <div className="text-3xl">🗺️</div>
            <h3 className="mt-2 text-sm font-semibold text-amber-800">地图加载失败</h3>
            <p className="mt-1.5 text-xs leading-relaxed text-amber-700">{error}</p>
            <ol className="mt-3 list-decimal text-left text-xs leading-relaxed text-amber-700">
              <li>前往 console.amap.com 创建应用，服务平台选「Web端(JS API)」</li>
              <li>复制 Key 和安全密钥（jscode）</li>
              <li>填入 frontend/.env.local（参考 .env.example）后重启 dev server</li>
            </ol>
          </div>
        </div>
      );
    }

    // relative z-0 创建独立堆叠上下文：高德内部 marker/InfoWindow 的 z-index（100+）
    // 若不加会与 TripPanel 的 z-10 在页面级竞争，盖住面板导致按钮无法点击
    return (
      <div className="relative z-0 h-full w-full">
        <div ref={containerRef} className="h-full w-full" />
        {!tilesReady && (
          <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-slate-50">
            <div className="flex flex-col items-center gap-2 text-sm text-slate-400">
              <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-brand-500" />
              地图加载中…
            </div>
          </div>
        )}
      </div>
    );
  },
);
