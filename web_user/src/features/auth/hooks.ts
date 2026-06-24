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
      const data = res.data;
      return {
        accessToken: data.accessToken,
        refreshToken: data.refreshToken,
        user: {
          id: data.userId,
          name: data.fullName,
          email: data.email,
          phone: data.phone,
          role: data.role,
          avatarUrl: data.avatarUrl,
        }
      } as unknown as SessionResponse;
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
    mutationFn: async (payload: { email: string; password: string; role: UserRole }) => {
      const res = await apiClient.post(endpoints.auth.login, payload);
      const data = res.data;
      return {
        accessToken: data.accessToken,
        refreshToken: data.refreshToken,
        user: {
          id: data.userId,
          name: data.fullName,
          email: data.email,
          phone: data.phone,
          role: data.role,
          avatarUrl: data.avatarUrl,
        }
      } as unknown as SessionResponse;
    },
    onSuccess: (data) => setSession(data),
  });
}
