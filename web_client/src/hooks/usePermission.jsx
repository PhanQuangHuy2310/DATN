import { createContext, useContext, useEffect, useState, useMemo } from "react";
import { api } from "../api.js";

export const PermissionContext = createContext(null);

const DEFAULT_ADMIN_ROLES = ["ADMIN", "OPS_ADMIN", "POLICY_ADMIN"];

/**
 * PermissionProvider supplies real-time module-level permissions for the authenticated user.
 * It initializes synchronously from `user.permissions` (if loaded with `api/v1/auth/me`),
 * and falls back to role matrix if unavailable.
 */
export function PermissionProvider({ user, children }) {
  // Permissions shipped with /auth/me win; otherwise fetch them once per user.
  const embedded = user?.permissions?.by_module;
  const [fetched, setFetched] = useState({ user: null, permissions: {} });

  useEffect(() => {
    if (!user || embedded) return undefined;
    let isMounted = true;
    api("/api/v1/permissions/me")
      .then((res) => isMounted && setFetched({ user, permissions: res?.permissions?.by_module || {} }))
      .catch(() => isMounted && setFetched({ user, permissions: {} }));
    return () => {
      isMounted = false;
    };
  }, [user, embedded]);

  const permissionsState = useMemo(() => {
    return embedded || (fetched.user === user ? fetched.permissions : {});
  }, [embedded, fetched, user]);
  const isLoading = Boolean(user && !embedded && fetched.user !== user);

  const value = useMemo(() => {
    return {
      permissions: permissionsState,
      isLoading,
      user,
    };
  }, [permissionsState, isLoading, user]);

  return (
    <PermissionContext.Provider value={value}>
      {children}
    </PermissionContext.Provider>
  );
}

/**
 * usePermission(moduleCode) hook
 * Returns { canView, canCreate, canUpdate, canDelete, isLoading }
 */
export function usePermission(moduleCode) {
  const context = useContext(PermissionContext);

  if (!context) {
    return {
      canView: true,
      canCreate: true,
      canUpdate: true,
      canDelete: true,
      isLoading: false,
    };
  }

  const { permissions, isLoading, user } = context;

  const modulePerms = permissions?.[moduleCode];
  if (modulePerms) {
    return {
      canView: Boolean(modulePerms.can_view),
      canCreate: Boolean(modulePerms.can_create),
      canUpdate: Boolean(modulePerms.can_update),
      canDelete: Boolean(modulePerms.can_delete),
      isLoading,
    };
  }

  const isSuperAdmin = user?.roles?.some((r) => DEFAULT_ADMIN_ROLES.includes(r));
  if (isSuperAdmin) {
    return {
      canView: true,
      canCreate: true,
      canUpdate: true,
      canDelete: true,
      isLoading,
    };
  }

  // Fallback defaults for unrecognized modules
  return {
    canView: true,
    canCreate: false,
    canUpdate: false,
    canDelete: false,
    isLoading,
  };
}

export default usePermission;
