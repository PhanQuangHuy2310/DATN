import { lazyWithPreload } from "./lazyWithPreload.jsx";

/** Imported only by web_admin/src/main.jsx; each screen is a lazy chunk. */
const named = (loader, name) => lazyWithPreload(() => loader().then((module) => ({ default: module[name] })));
const adminModule = () => import("./components/Admin.jsx");
const adminPagesModule = () => import("./components/AdminPages.jsx");

export const adminScreens = Object.freeze({
  AdminDashboard: named(adminPagesModule, "AdminDashboard"),
  OperationsPage: named(adminPagesModule, "OperationsPage"),
  SlaNotificationsPage: named(adminPagesModule, "SlaNotificationsPage"),
  SystemConfigPage: named(adminPagesModule, "SystemConfigPage"),
  PolicyWorkspace: named(adminPagesModule, "PolicyWorkspace"),
  AuditLogPage: named(adminPagesModule, "AuditLogPage"),
  AiPolicyAdmin: lazyWithPreload(() => import("./components/AiPolicyAdmin.jsx")),
  AuditorWorkspace: lazyWithPreload(() => import("./components/AuditorWorkspace.jsx")),
  IdentityAdmin: lazyWithPreload(() => import("./components/IdentityAdmin.jsx")),
  OrgChart: lazyWithPreload(() => import("./components/OrgChart.jsx")),
  ApiAdministration: lazyWithPreload(() => import("./components/ApiAdministration.jsx")),
  PlanCatalog: lazyWithPreload(() => import("./components/PlanCatalog.jsx")),
  RequestWorkflowsPage: lazyWithPreload(() => import("./components/RequestWorkflowsPage.jsx")),
  UserManagementPage: lazyWithPreload(() => import("./components/UserManagementPage.jsx")),
  RolePermissionMatrixPage: lazyWithPreload(() => import("./components/RolePermissionMatrixPage.jsx")),
  RegulationsManagementPage: lazyWithPreload(() => import("./components/RegulationsManagementPage.jsx")),
  AiEngineManagementPage: lazyWithPreload(() => import("./components/AiEngineManagementPage.jsx")),
  SystemVersionsPage: lazyWithPreload(() => import("./components/SystemVersionsPage.jsx")),
  AdminEvents: named(adminModule, "AdminEvents"),
  Operations: named(adminModule, "Operations"),
  Policy: named(adminModule, "Policy"),
  /** Warm every admin screen after sign-in (see prefetch.js). */
  preload: () => {
    for (const screen of Object.values(adminScreens)) screen.preload?.();
  },
});
