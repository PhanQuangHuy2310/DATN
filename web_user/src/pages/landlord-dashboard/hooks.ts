import { useQuery } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";

export interface DailyStat {
  date: string;
  views: number;
  contacts: number;
  bookings: number;
}

export interface LandlordStats {
  plan: "FREE" | "PRO";
  activeCount: number;
  quota: number; // -1 = unlimited (PRO)
  daily: DailyStat[];
}

export function useLandlordStats() {
  return useQuery({
    queryKey: ["landlord", "stats"],
    queryFn: async () => {
      const res = await apiClient.get<LandlordStats>(endpoints.stats.listings);
      return res.data;
    },
  });
}
