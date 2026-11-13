import { getResource } from "./api.js";
import { ADMIN_API, WORKSPACE_API } from "./apiBase.js";
import { teamReportUrl } from "./components/TeamDashboard.jsx";

/** GET URLs each page asks for on open, exactly as the page builds them, so a
 * prefetched response is the one the page later finds in the cache. */
function pageUrls(base, canDelegate) {
  return {
    requests: [
      `${WORKSPACE_API}/request-catalog`,
      `${WORKSPACE_API}/my-requests?r=0`,
      "/api/v1/requests?limit=20&offset=0&tab=mine&_revision=0",
      "/api/v1/requests?limit=20&offset=0&tab=approval&_revision=0",
      "/api/v1/request-types",
      "/api/v1/meta/org-chart",
      `${WORKSPACE_API}/workflow-categories`,
      `${WORKSPACE_API}/request-templates`,
      `${WORKSPACE_API}/mock-apis`,
    ],
    "request-catalog": [`${ADMIN_API}/workflow-categories`, `${ADMIN_API}/request-templates`, `${ADMIN_API}/mock-apis`],
    "org-client": [`${WORKSPACE_API}/org-chart-tree`],
    "org-chart": [`${ADMIN_API}/org-chart-tree`],
    people: [`${base}/users-management?limit=200&t=0`, `${base}/rbac/roles`, `${base}/departments?limit=100`],
    users: [`${base}/users-management?limit=200&t=0`, `${base}/rbac/roles`, `${base}/departments?limit=100`],
    permissions: [`${ADMIN_API}/rbac/roles`, `${ADMIN_API}/users-management?limit=200`, `${ADMIN_API}/rbac/matrix?role_id=STAFF`],
    "regulations-view": [`${base}/regulations`],
    policy: [`${base}/regulations`],
    "ai-policy": [`${ADMIN_API}/request-templates`],
    "api-admin": [`${ADMIN_API}/mock-apis`],
    system: [`${ADMIN_API}/system-versions/changelog`],
    team: [teamReportUrl()],
    "team-employees": [teamReportUrl()],
    profile: canDelegate ? ["/api/v1/delegations", "/api/v1/delegations/candidates"] : [],
  };
}

/** After sign-in, quietly load every page the user can open: its code via
 * preloadCode, its data a few requests at a time. Switching pages then paints
 * from cache instead of waiting on the database. Failures are ignored: the
 * page simply loads normally. */
export function prefetchPages(pageKeys, portal, roles = [], preloadCode = null) {
  const map = pageUrls(portal === "admin" ? ADMIN_API : WORKSPACE_API, roles.includes("APPROVER"));
  const queue = [...new Set(pageKeys.flatMap((key) => map[key] || []))];
  const worker = async () => {
    while (queue.length) {
      const url = queue.shift();
      try { await getResource(url); } catch { /* the page will load it on open */ }
    }
  };
  const start = () => {
    preloadCode?.(); // page code first: it is local and makes first visits synchronous
    for (let i = 0; i < 3; i += 1) void worker();
  };
  if (typeof window.requestIdleCallback === "function") window.requestIdleCallback(start, { timeout: 2000 });
  else setTimeout(start, 800);
}
