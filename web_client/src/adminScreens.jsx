import { lazy } from "react";

/** Imported only by web_admin/src/main.jsx; each screen is a lazy chunk. */
const named = (loader, name) => lazy(() => loader().then((module) => ({ default: module[name] })));
const adminModule = () => import("./components/Admin.jsx");

export const adminScreens = Object.freeze({
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
