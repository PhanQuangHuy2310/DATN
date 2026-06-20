import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { Appointment } from "@/entities/appointment";

export interface Slot {
  /** ISO datetime of the slot start. */
  time: string;
  available: boolean;
}

export function useListingSlots(listingId: number | string, enabled = true) {
  return useQuery({
    queryKey: ["slots", listingId],
    enabled,
    queryFn: async () => {
      const res = await apiClient.get<Slot[]>(endpoints.appointments.slots(listingId));
      return res.data;
    },
  });
}

export interface CreateAppointmentPayload {
  listingId: number;
  appointmentTime: string;
  note?: string;
}

export function useCreateAppointment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateAppointmentPayload) => {
      const res = await apiClient.post<Appointment>(endpoints.appointments.base, payload);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["appointments"] }),
  });
}
