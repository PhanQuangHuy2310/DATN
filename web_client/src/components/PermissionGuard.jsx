import React from "react";
import { usePermission } from "../hooks/usePermission.jsx";

/**
 * PermissionGuard conditionally displays or disables actions based on permissions.
 *
 * Usage:
 * <PermissionGuard module="users" action="create">
 *   <button onClick={handleCreate}>Tạo người dùng</button>
 * </PermissionGuard>
 */
export function PermissionGuard({
  module,
  action = "view",
  fallback = null,
  disableInsteadOfHide = false,
  children,
}) {
  const perms = usePermission(module);
  const actionKey =
    action === "create"
      ? "canCreate"
      : action === "update"
      ? "canUpdate"
      : action === "delete"
      ? "canDelete"
      : "canView";

  const allowed = perms[actionKey];

  if (allowed) {
    return children;
  }

  if (disableInsteadOfHide && React.isValidElement(children)) {
    return React.cloneElement(children, {
      disabled: true,
      title: "Bạn không có quyền thực hiện thao tác này",
      "aria-disabled": "true",
      style: {
        ...(children.props.style || {}),
        opacity: 0.5,
        cursor: "not-allowed",
      },
    });
  }

  return fallback;
}

export default PermissionGuard;

