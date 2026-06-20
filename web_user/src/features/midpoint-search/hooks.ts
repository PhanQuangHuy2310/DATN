import { useMutation } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { Listing } from "@/entities/listing";
import type { LatLng } from "@/shared/types";

export interface MidpointResult {
  midpoint: LatLng;
  listings: Listing[];
}

export function useMidpointSearch() {
  return useMutation({
    mutationFn: async (coordinates: LatLng[]) => {
      const res = await apiClient.post<MidpointResult>(
        endpoints.listings.midpointSearch,
        { coordinates },
      );
      return res.data;
    },
  });
}
