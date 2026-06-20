import { useMutation } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { User } from "@/entities/user";
import type { UserRole } from "@/shared/types";
import { useAuthStore } from "./authStore";

export interface SessionResponse {
  accessToken: string;
  refreshToken: string;
  user: User;
}

export interface RegisterPayload {
  fullName: string;
  email: string;
  phone: string;
  password: string;
  role: UserRole;
}

export function useRegister() {
  return useMutation({
    mutationFn: async (payload: RegisterPayload) => {
      const res = await apiClient.post(endpoints.auth.register, payload);
      return res.data as { status: string; message: string };
    },
  });
}

export function useVerifyOtp() {
  const setSession = useAuthStore((s) => s.setSession);
  return useMutation({
    mutationFn: async (payload: { email: string; otpCode: string }) => {
      const res = await apiClient.post(endpoints.auth.verifyOtp, payload);
      return res.data as SessionResponse;
    },
    onSuccess: (data) => setSession(data),
  });
}

export function useResendOtp() {
  return useMutation({
    mutationFn: async (email: string) => {
      const res = await apiClient.post(endpoints.auth.resendOtp, { email });
      return res.data;
    },
  });
}

export function useLogin() {
  const setSession = useAuthStore((s) => s.setSession);
  return useMutation({
    mutationFn: async (payload: { email: string; password: string }) => {
      const res = await apiClient.post(endpoints.auth.login, payload);
      return res.data as SessionResponse;
    },
    onSuccess: (data) => setSession(data),
  });
}
