import { useQuery } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { Listing } from "@/entities/listing";

/** Small read-only home-page feeds. Each tolerates an empty/missing backend. */
function useListingFeed(key: string, url: string) {
  return useQuery({
    queryKey: ["home", key],
    queryFn: async () => {
      const res = await apiClient.get<Listing[]>(url);
      return res.data;
    },
  });
}

export const useLatestListings = () => useListingFeed("latest", endpoints.listings.latest);
export const useFeaturedListings = () => useListingFeed("featured", endpoints.listings.featured);
export const useRoommateListings = () => useListingFeed("roommates", endpoints.listings.roommates);
