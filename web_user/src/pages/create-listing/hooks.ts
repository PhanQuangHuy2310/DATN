import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { Listing } from "@/entities/listing";

export type ListingPayload = Partial<Listing> & {
  title: string;
  price: number;
  area: number;
};

export function useCreateListing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ListingPayload) => {
      const res = await apiClient.post<Listing>(endpoints.listings.base, payload);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["listings"] }),
  });
}

export function useUpdateListing(id: number | string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ListingPayload) => {
      const res = await apiClient.put<Listing>(endpoints.listings.byId(id), payload);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["listings"] });
      qc.invalidateQueries({ queryKey: ["listing", String(id)] });
    },
  });
}
