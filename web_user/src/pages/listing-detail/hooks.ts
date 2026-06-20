import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { Listing } from "@/entities/listing";
import type { Review } from "@/entities/review";

export interface Poi {
  id: string | number;
  name: string;
  category: string;
  distance: number;
}

export function useListing(id: string | number) {
  return useQuery({
    queryKey: ["listing", String(id)],
    queryFn: async () => {
      const res = await apiClient.get<Listing>(endpoints.listings.byId(id));
      return res.data;
    },
  });
}

export function useListingPoi(id: string | number, enabled = true) {
  return useQuery({
    queryKey: ["listing", String(id), "poi"],
    enabled,
    queryFn: async () => {
      const res = await apiClient.get<Poi[]>(endpoints.listings.poi(id));
      return res.data;
    },
  });
}

export function useListingReviews(id: string | number) {
  return useQuery({
    queryKey: ["listing", String(id), "reviews"],
    queryFn: async () => {
      const res = await apiClient.get<Review[]>(endpoints.reviews.byListing(id));
      return res.data;
    },
  });
}

export function useSubmitReview(listingId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { rating: number; content: string }) => {
      const res = await apiClient.post<Review>(endpoints.reviews.base, {
        listingId,
        ...payload,
      });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["listing", String(listingId), "reviews"] });
      qc.invalidateQueries({ queryKey: ["listing", String(listingId)] });
    },
  });
}

export interface StartChatResponse {
  conversationId: number;
}

export function useStartChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (listingId: number) => {
      const res = await apiClient.post<StartChatResponse>(endpoints.conversations.start, {
        listingId,
      });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
