import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuthStore } from "@/features/auth/authStore";
import type { UserRole } from "@/shared/types";

interface ProtectedRouteProps {
  children: ReactNode;
  roles?: UserRole[];
}

export function ProtectedRoute({ children, roles }: ProtectedRouteProps) {
  const { isAuthenticated, user, hydrated } = useAuthStore();
  const location = useLocation();

  if (!hydrated) return null;

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (roles && user && !roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
