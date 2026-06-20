import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { Appointment, AppointmentStatus } from "@/entities/appointment";

export function useAppointments() {
  return useQuery({
    queryKey: ["appointments"],
    queryFn: async () => {
      const res = await apiClient.get<Appointment[]>(endpoints.appointments.base);
      return res.data;
    },
  });
}

export function useUpdateAppointmentStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { id: number; status: AppointmentStatus; reason?: string }) => {
      const res = await apiClient.patch<Appointment>(endpoints.appointments.status(vars.id), {
        status: vars.status,
        cancelReason: vars.reason,
      });
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["appointments"] }),
  });
}
