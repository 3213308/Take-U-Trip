import type { Itinerary } from "@/types/itinerary";
import type { GeoPoint } from "@/stores/mapStore";
import { createJSONRepository } from "./local";
import { ItineraryHttpRepo } from "./http";

// 行程：走后端 API（agent 自动保存，前端只读）
export const itineraryRepo = new ItineraryHttpRepo();

// 愿望清单：操作即保存，走 stores/wishlistStore 内联的 wishlistApi

// 聊天历史：走后端 checkpoint（GET /api/chat/history），不再用 localStorage

// 地图状态：纯 UI 状态，留 localStorage
export const mapRepo = createJSONRepository<{
  selectedDayIndex: number;
  panelCollapsed: boolean;
  geocodeCache: Record<string, GeoPoint>;
}>({
  key: "tut:v1:map",
  version: 1,
});
