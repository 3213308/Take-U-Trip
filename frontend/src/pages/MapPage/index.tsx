import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useItineraryStore } from "@/stores/itineraryStore";
import { useMapStore } from "@/stores/mapStore";
import { MapCanvas, type MapCanvasHandle } from "./MapCanvas";
import { TripPanel } from "./TripPanel";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export function MapPage() {
  const itinerary = useItineraryStore((s) => s.itinerary);
  const hydrated = useItineraryStore((s) => s.hydrated);
  const selectedDayIndex = useMapStore((s) => s.selectedDayIndex);
  const setDay = useMapStore((s) => s.setDay);
  const navigate = useNavigate();

  const canvasRef = useRef<MapCanvasHandle>(null);
  const [missLocations, setMissLocations] = useState<string[]>([]);

  // 天索引可能超过行程天数（行程被编辑后），钳制
  const dayIndex = Math.min(selectedDayIndex, Math.max(0, (itinerary?.days_plan.length ?? 1) - 1));
  const day = itinerary?.days_plan[dayIndex];

  useEffect(() => {
    if (selectedDayIndex !== dayIndex) setDay(dayIndex);
  }, [selectedDayIndex, dayIndex, setDay]);

  const focusActivity = useCallback((index: number) => {
    return canvasRef.current?.focusActivity(index) ?? false;
  }, []);

  const onMissChange = useCallback((miss: string[]) => {
    setMissLocations(miss);
  }, []);

  if (!hydrated) {
    return <div className="p-8 text-sm text-slate-300">加载中…</div>;
  }

  if (!itinerary || !day || itinerary.days_plan.length === 0) {
    return (
      <div className="h-full">
        <EmptyState
          icon="🗺️"
          title="还没有可展示的行程"
          description="生成行程后，这里会在地图上标出每天的路线，左上角卡片会告诉你下一步去哪"
          action={
            <Button onClick={() => navigate("/chat")}>去生成行程</Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="relative h-full">
      <MapCanvas
        ref={canvasRef}
        activities={day.activities}
        destination={itinerary.destination}
        onMissChange={onMissChange}
      />
      <TripPanel
        itinerary={itinerary}
        dayIndex={dayIndex}
        day={day}
        focusActivity={focusActivity}
        missLocations={missLocations}
      />
    </div>
  );
}
