import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";
import { config } from "@/shared/config";
import { tokenStorage, emitLogout } from "./tokenStorage";

export const apiClient = axios.create({
  baseURL: config.apiBaseUrl,
  headers: { "Content-Type": "application/json" },
  timeout: 20000,
});

apiClient.interceptors.request.use((req: InternalAxiosRequestConfig) => {
  const token = tokenStorage.getAccess();
  if (token) req.headers.Authorization = `Bearer ${token}`;
  return req;
});

/* ---- Refresh-token flow: dedupe concurrent 401s into one refresh call ---- */
let refreshing: Promise<string | null> | null = null;

async function runRefresh(): Promise<string | null> {
  const refreshToken = tokenStorage.getRefresh();
  if (!refreshToken) return null;
  try {
    const { data } = await axios.post(
      `${config.apiBaseUrl}/api/auth/refresh`,
      { refreshToken },
      { headers: { "Content-Type": "application/json" } },
    );
    tokenStorage.set(data.accessToken, data.refreshToken);
    return data.accessToken as string;
  } catch {
    return null;
  }
}

export const API_ERROR_EVENT = "api-error";

apiClient.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as
      | (AxiosRequestConfig & { _retried?: boolean })
      | undefined;

    const isAuthCall = original?.url?.includes("/api/auth/");
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      refreshing = refreshing ?? runRefresh();
      const newToken = await refreshing;
      refreshing = null;

      if (newToken) {
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization = `Bearer ${newToken}`;
        return apiClient(original);
      }
      tokenStorage.clear();
      emitLogout();
    }

    // --- Bắt đầu phần Global Error Logging ---
    // Log chi tiết lỗi ra console để dev dễ debug
    console.group(`🚨 API Error: ${original?.method?.toUpperCase()} ${original?.url}`);
    console.error("Status:", error.response?.status);
    console.error("Payload:", original?.data);
    console.error("Response:", error.response?.data);
    console.error("Full Error:", error);
    console.groupEnd();

    // Bắn sự kiện ra ngoài để UI hiển thị Toast notification
    const errorMessage = getErrorMessage(error);
    window.dispatchEvent(
      new CustomEvent(API_ERROR_EVENT, { detail: errorMessage })
    );
    // --- Kết thúc ---

    return Promise.reject(error);
  },
);

/** Normalise an axios error into a human Vietnamese message. */
export function getErrorMessage(err: unknown, fallback = "Đã có lỗi xảy ra, vui lòng thử lại."): string {
  if (axios.isAxiosError(err)) {
    return (
      (err.response?.data as { message?: string } | undefined)?.message ??
      err.message ??
      fallback
    );
  }
  return fallback;
}
