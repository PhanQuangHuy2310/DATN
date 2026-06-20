import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { Listing, ListingStatus } from "@/entities/listing";

export function useMyListings() {
  return useQuery({
    queryKey: ["listings", "mine"],
    queryFn: async () => {
      const res = await apiClient.get<Listing[]>(endpoints.listings.mine);
      return res.data;
    },
  });
}

export function useToggleListingStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { id: number; status: ListingStatus }) => {
      const res = await apiClient.patch(endpoints.listings.status(vars.id), {
        status: vars.status,
      });
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["listings", "mine"] }),
  });
}

export function useCloneListing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await apiClient.post<Listing>(endpoints.listings.clone(id));
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["listings", "mine"] }),
  });
}

export function useDeleteListing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(endpoints.listings.byId(id));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["listings", "mine"] }),
  });
}

export interface CreatePaymentResponse {
  paymentUrl: string;
  transactionId: string;
}

export function useCreatePayment() {
  return useMutation({
    mutationFn: async (vars: { plan: "PRO"; provider: "MOMO" | "ZALOPAY" }) => {
      const res = await apiClient.post<CreatePaymentResponse>(
        endpoints.payments.create,
        vars,
      );
      return res.data;
    },
  });
}
