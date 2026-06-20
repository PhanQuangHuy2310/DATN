import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { User } from "@/entities/user";
import type { ListingFilters } from "@/features/search-listings";

export interface SavedFilter {
  id: number;
  name: string;
  criteria: ListingFilters;
  notifyEmail: boolean;
  notifyInApp: boolean;
  createdAt?: string;
}

export type VerificationStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface VerificationRequest {
  id: number;
  status: VerificationStatus;
  idCardUrl?: string;
  ownershipUrl?: string;
  note?: string;
  createdAt?: string;
}

export function useUpdateProfile() {
  return useMutation({
    mutationFn: async (payload: Partial<User>) => {
      const res = await apiClient.put<User>(endpoints.profile.base, payload);
      return res.data;
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (payload: { currentPassword: string; newPassword: string }) => {
      const res = await apiClient.put(endpoints.profile.password, payload);
      return res.data;
    },
  });
}

export function useSavedFilters() {
  return useQuery({
    queryKey: ["saved-filters"],
    queryFn: async () => {
      const res = await apiClient.get<SavedFilter[]>(endpoints.savedFilters.base);
      return res.data;
    },
  });
}

export function useUpdateSavedFilter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { id: number; notifyEmail?: boolean; notifyInApp?: boolean }) => {
      const res = await apiClient.patch(`${endpoints.savedFilters.base}/${vars.id}`, vars);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-filters"] }),
  });
}

export function useDeleteSavedFilter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`${endpoints.savedFilters.base}/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-filters"] }),
  });
}

export function useVerificationRequests() {
  return useQuery({
    queryKey: ["verification"],
    queryFn: async () => {
      const res = await apiClient.get<VerificationRequest[]>(endpoints.verification.base);
      return res.data;
    },
  });
}

export function useSubmitVerification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { idCardUrl: string; ownershipUrl: string }) => {
      const res = await apiClient.post<VerificationRequest>(endpoints.verification.base, payload);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["verification"] }),
  });
}
