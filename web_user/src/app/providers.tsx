import { useEffect, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider, useToast } from "@/shared/ui";
import { AUTH_LOGOUT_EVENT, API_ERROR_EVENT } from "@/shared/api";
import { useAuthStore } from "@/features/auth/authStore";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

/** Lắng nghe lỗi API toàn cục để hiển thị Toast */
function GlobalErrorBridge() {
  const toast = useToast();

  useEffect(() => {
    const onError = (e: Event) => {
      const customEvent = e as CustomEvent<string>;
      // Nếu là lỗi 401 thì không hiện toast báo lỗi chung vì AuthBridge đã xử lý logout
      // hoặc bạn có thể hiện "Phiên đăng nhập hết hạn" ở đây.
      // Tạm thời các lỗi API khác sẽ đều hiện toast đỏ.
      if (customEvent.detail) {
        toast.show(customEvent.detail, "error");
      }
    };
    window.addEventListener(API_ERROR_EVENT, onError);
    return () => window.removeEventListener(API_ERROR_EVENT, onError);
  }, [toast]);

  return null;
}

/** Hydrates the auth store and reacts to forced logout from the API client. */
function AuthBridge({ children }: { children: ReactNode }) {
  const hydrate = useAuthStore((s) => s.hydrate);
  const logout = useAuthStore((s) => s.logout);

  useEffect(() => {
    hydrate();
    const onLogout = () => {
      // Optional: có thể hiện toast thông báo hết hạn phiên
      logout();
    };
    window.addEventListener(AUTH_LOGOUT_EVENT, onLogout);
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, onLogout);
  }, [hydrate, logout]);

  return <>{children}</>;
}

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <GlobalErrorBridge />
        <AuthBridge>{children}</AuthBridge>
      </ToastProvider>
    </QueryClientProvider>
  );
}
