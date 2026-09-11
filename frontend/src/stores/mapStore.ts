import { create } from "zustand";

export interface GeoPoint {
  lng: number;
  lat: number;
}

const CACHE_LIMIT = 500;

interface MapState {
  selectedDayIndex: number;
  /** 当前选中的活动在原数组中的索引，-1 表示未选中 */
  selectedActivityOrigIdx: number;
  panelCollapsed: boolean;
  geocodeCache: Record<string, GeoPoint>;
  hydrated: boolean;

  hydrate: (data: {
    selectedDayIndex: number;
    selectedActivityOrigIdx?: number;
    panelCollapsed: boolean;
    geocodeCache: Record<string, GeoPoint>;
  } | null) => void;
  setDay: (index: number) => void;
  setSelectedActivity: (origIdx: number) => void;
  setPanelCollapsed: (collapsed: boolean) => void;
  togglePanel: () => void;
  getGeocode: (key: string) => GeoPoint | undefined;
  putGeocode: (key: string, point: GeoPoint) => void;
}

export const useMapStore = create<MapState>((set, get) => ({
  selectedDayIndex: 0,
  selectedActivityOrigIdx: -1,
  panelCollapsed: false,
  geocodeCache: {},
  hydrated: false,

  hydrate: (data) =>
    set({
      selectedDayIndex: data?.selectedDayIndex ?? 0,
      selectedActivityOrigIdx: data?.selectedActivityOrigIdx ?? -1,
      panelCollapsed: data?.panelCollapsed ?? false,
      geocodeCache: data?.geocodeCache ?? {},
      hydrated: true,
    }),

  setDay: (index) => set({ selectedDayIndex: index, selectedActivityOrigIdx: -1 }),

  setSelectedActivity: (origIdx) => set({ selectedActivityOrigIdx: origIdx }),

  setPanelCollapsed: (collapsed) => set({ panelCollapsed: collapsed }),

  togglePanel: () => set((s) => ({ panelCollapsed: !s.panelCollapsed })),

  getGeocode: (key) => get().geocodeCache[key],

  putGeocode: (key, point) =>
    set((s) => {
      const cache = { ...s.geocodeCache, [key]: point };
      const keys = Object.keys(cache);
      if (keys.length > CACHE_LIMIT) {
        for (const k of keys.slice(0, keys.length - CACHE_LIMIT)) delete cache[k];
      }
      return { geocodeCache: cache };
    }),
}));
