export type WishSource = "manual" | "itinerary";

export interface WishItem {
  id: string;
  name: string;
  location: string;
  /** 所在城市，用于分组统计 */
  city: string;
  source: WishSource;
  notes?: string;
  completed: boolean;
  completedAt: string | null;
  createdAt: string;
}
