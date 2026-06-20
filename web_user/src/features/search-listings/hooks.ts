import { useQuery } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { Listing, ListingPin, ListingType } from "@/entities/listing";
import type { Page } from "@/shared/types";
import type { ListingFilters } from "./types";
import { filtersToParams } from "./filterParams";

export function useSearchListings(filters: ListingFilters) {
  return useQuery({
    queryKey: ["listings", "search", filters],
    queryFn: async () => {
      const res = await apiClient.get<Page<Listing>>(endpoints.listings.search, {
        params: filtersToParams(filters),
      });
      return res.data;
    },
  });
}

export interface MapQuery {
  lat: number;
  lng: number;
  radius: number;
  type?: ListingType;
}

export function useMapListings(query: MapQuery | null) {
  return useQuery({
    queryKey: ["listings", "map", query],
    enabled: !!query,
    queryFn: async () => {
      const res = await apiClient.get<ListingPin[]>(endpoints.listings.map, {
        params: query!,
      });
      return res.data;
    },
  });
}
