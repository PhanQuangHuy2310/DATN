import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { Listing } from "@/entities/listing";

export function useWishlist(enabled = true) {
  return useQuery({
    queryKey: ["wishlist"],
    enabled,
    queryFn: async () => {
      const res = await apiClient.get<Listing[]>(endpoints.wishlist.base);
      return res.data;
    },
  });
}

/** Toggle a listing in the wishlist; invalidates the wishlist + search caches. */
export function useToggleWishlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (listingId: number) => {
      const res = await apiClient.put<{ favorite: boolean }>(
        endpoints.wishlist.toggle(listingId),
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wishlist"] });
      qc.invalidateQueries({ queryKey: ["listings"] });
    },
  });
}
