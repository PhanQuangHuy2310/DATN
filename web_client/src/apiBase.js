import { createContext, useContext } from "react";

/** Screens shared by both portals call `${useApiBase()}/...`: the admin portal
 * uses /api/v1/admin, the employee portal /api/v1/workspace (module rights). */
export const ADMIN_API = "/api/v1/admin";
export const WORKSPACE_API = "/api/v1/workspace";
export const ApiBaseContext = createContext(ADMIN_API);
export const useApiBase = () => useContext(ApiBaseContext);
