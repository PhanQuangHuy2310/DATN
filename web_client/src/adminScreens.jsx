import { lazy } from "react";

/** Imported only by web_admin/src/main.jsx; each screen is a lazy chunk. */
const named = (loader, name) => lazy(() => loader().then((module) => ({ default: module[name] })));
const adminModule = () => import("./components/Admin.jsx");
const adminPagesModule = () => import("./components/AdminPages.jsx");

export const adminScreens = Object.freeze({
  AdminDashboard: named(adminPagesModule, "AdminDashboard"),
  OperationsPage: named(adminPagesModule, "OperationsPage"),
  SlaNotificationsPage: named(adminPagesModule, "SlaNotificationsPage"),
  SystemConfigPage: named(adminPagesModule, "SystemConfigPage"),
  PolicyWorkspace: named(adminPagesModule, "PolicyWorkspace"),
  AuditLogPage: named(adminPagesModule, "AuditLogPage"),
  AiPolicyAdmin: lazy(() => import("./components/AiPolicyAdmin.jsx")),
  AuditorWorkspace: lazy(() => import("./components/AuditorWorkspace.jsx")),
  IdentityAdmin: lazy(() => import("./components/IdentityAdmin.jsx")),
  OrgChart: lazy(() => import("./components/OrgChart.jsx")),
  ApiAdministration: lazy(() => import("./components/ApiAdministration.jsx")),
  PlanCatalog: lazy(() => import("./components/PlanCatalog.jsx")),
  AdminEvents: named(adminModule, "AdminEvents"),
  Operations: named(adminModule, "Operations"),
  Policy: named(adminModule, "Policy"),
});
