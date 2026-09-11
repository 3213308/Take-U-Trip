import { create } from "zustand";
import type { Activity, DayPlan, Itinerary } from "@/types/itinerary";
import { addDays, todayStr } from "@/lib/utils/date";

interface ItineraryState {
  itinerary: Itinerary | null;
  hydrated: boolean;
  hydrate: (data: Itinerary | null) => void;
  setItinerary: (it: Itinerary) => void;
  clearItinerary: () => void;

  updateMeta: (patch: Partial<Pick<Itinerary, "destination" | "total_budget">>) => void;
  updateDay: (dayIndex: number, patch: Partial<Pick<DayPlan, "date" | "theme" | "daily_budget">>) => void;
  insertDay: (atIndex: number) => void;
  removeDay: (dayIndex: number) => void;

  addActivity: (dayIndex: number, activity: Activity) => void;
  updateActivity: (dayIndex: number, activityIndex: number, patch: Partial<Activity>) => void;
  removeActivity: (dayIndex: number, activityIndex: number) => void;
  moveActivity: (dayIndex: number, from: number, to: number) => void;
}

function withSortedActivities(day: DayPlan): DayPlan {
  return {
    ...day,
    activities: [...day.activities].sort((a, b) => a.time.localeCompare(b.time)),
  };
}

export const useItineraryStore = create<ItineraryState>((set) => ({
  itinerary: null,
  hydrated: false,

  hydrate: (data) => set({ itinerary: data, hydrated: true }),

  setItinerary: (it) => set({ itinerary: it }),

  clearItinerary: () => set({ itinerary: null }),

  updateMeta: (patch) =>
    set((s) => (s.itinerary ? { itinerary: { ...s.itinerary, ...patch } } : {})),

  updateDay: (dayIndex, patch) =>
    set((s) => {
      if (!s.itinerary) return {};
      const days = [...s.itinerary.days_plan];
      days[dayIndex] = { ...days[dayIndex], ...patch };
      return { itinerary: { ...s.itinerary, days_plan: days } };
    }),

  insertDay: (atIndex) =>
    set((s) => {
      if (!s.itinerary) return {};
      const days = [...s.itinerary.days_plan];
      const newDate =
        days.length === 0
          ? todayStr()
          : atIndex === 0
            ? addDays(days[0].date, -1)
            : addDays(days[atIndex - 1].date, 1);
      const newDay: DayPlan = {
        date: newDate,
        theme: "",
        activities: [],
        daily_budget: 0,
      };
      days.splice(atIndex, 0, newDay);
      // 重排后续日期，保证严格递增不重复
      for (let i = atIndex + 1; i < days.length; i++) {
        days[i] = { ...days[i], date: addDays(days[i - 1].date, 1) };
      }
      return {
        itinerary: { ...s.itinerary, days_plan: days, days: days.length },
      };
    }),

  removeDay: (dayIndex) =>
    set((s) => {
      if (!s.itinerary) return {};
      const days = s.itinerary.days_plan.filter((_, i) => i !== dayIndex);
      return {
        itinerary: { ...s.itinerary, days_plan: days, days: days.length },
      };
    }),

  addActivity: (dayIndex, activity) =>
    set((s) => {
      if (!s.itinerary) return {};
      const days = [...s.itinerary.days_plan];
      days[dayIndex] = withSortedActivities({
        ...days[dayIndex],
        activities: [...days[dayIndex].activities, activity],
      });
      return { itinerary: { ...s.itinerary, days_plan: days } };
    }),

  updateActivity: (dayIndex, activityIndex, patch) =>
    set((s) => {
      if (!s.itinerary) return {};
      const days = [...s.itinerary.days_plan];
      const acts = [...days[dayIndex].activities];
      acts[activityIndex] = { ...acts[activityIndex], ...patch };
      days[dayIndex] = withSortedActivities({ ...days[dayIndex], activities: acts });
      return { itinerary: { ...s.itinerary, days_plan: days } };
    }),

  removeActivity: (dayIndex, activityIndex) =>
    set((s) => {
      if (!s.itinerary) return {};
      const days = [...s.itinerary.days_plan];
      days[dayIndex] = {
        ...days[dayIndex],
        activities: days[dayIndex].activities.filter((_, i) => i !== activityIndex),
      };
      return { itinerary: { ...s.itinerary, days_plan: days } };
    }),

  moveActivity: (dayIndex, from, to) =>
    set((s) => {
      if (!s.itinerary) return {};
      const days = [...s.itinerary.days_plan];
      const acts = [...days[dayIndex].activities];
      if (to < 0 || to >= acts.length || from === to) return {};
      const [moved] = acts.splice(from, 1);
      acts.splice(to, 0, moved);
      days[dayIndex] = { ...days[dayIndex], activities: acts };
      return { itinerary: { ...s.itinerary, days_plan: days } };
    }),
}));
