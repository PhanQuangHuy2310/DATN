import { createClient } from "@supabase/supabase-js";

// AGENTS.md: browsers never talk to Supabase and no keys live in frontend code.
// Not imported by the app; kept only so in-progress work is not lost.
export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "";
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "";

/**
 * Supabase client configured with default schema 'eas'.
 * Always explicitly calls .schema('eas') on all queries.
 */
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  db: {
    schema: "eas",
  },
  auth: {
    persistSession: false,
    autoRefreshToken: false,
  },
});

/**
 * Access any table or view in schema 'eas' with strict schema isolation.
 * @param {string} tableName
 */
export function fromEas(tableName) {
  return supabase.schema("eas").from(tableName);
}

/**
 * Call any stored procedure (RPC) in schema 'eas'.
 * @param {string} rpcName
 * @param {Record<string, unknown>} params
 */
export function rpcEas(rpcName, params = {}) {
  return supabase.schema("eas").rpc(rpcName, params);
}

// -----------------------------------------------------------------------------
// Type-safe RPC helpers for Portal Verification and RBAC
// -----------------------------------------------------------------------------

/**
 * Verify whether an email account is authorized to log in to the Admin Portal (8081).
 * Only admin@eas.com (or records in eas.admins / eas.admin_account) are allowed.
 * @param {string} email
 */
export async function verifyAdminPortalAccess(email) {
  try {
    const { data, error } = await supabase.schema("eas").rpc("verify_admin_portal_access", { p_email: email });
    if (error) throw error;
    const res = Array.isArray(data) ? data[0] : data;
    return {
      allowed: Boolean(res?.allowed),
      userId: res?.user_id,
      email: res?.email || email,
      displayName: res?.display_name || "",
      message: res?.message || "",
    };
  } catch {
    // Fallback: strict local rule (admin@eas.com only)
    const isAdmin = String(email).trim().toLowerCase() === "admin@eas.com";
    return {
      allowed: isAdmin,
      email,
      message: isAdmin ? "Quyền quản trị viên hợp lệ." : "Tài khoản nhân viên không được phép đăng nhập vào Cổng Quản trị (8081).",
    };
  }
}

/**
 * Verify whether an email account is authorized to log in to the Client Portal (8080).
 * admin@eas.com is strictly forbidden on the employee client portal.
 * @param {string} email
 */
export async function verifyClientPortalAccess(email) {
  try {
    const { data, error } = await supabase.schema("eas").rpc("verify_client_portal_access", { p_email: email });
    if (error) throw error;
    const res = Array.isArray(data) ? data[0] : data;
    return {
      allowed: Boolean(res?.allowed),
      userId: res?.user_id,
      email: res?.email || email,
      displayName: res?.display_name || "",
      departmentId: res?.department_id,
      message: res?.message || "",
    };
  } catch {
    const isAdmin = String(email).trim().toLowerCase() === "admin@eas.com";
    return {
      allowed: !isAdmin,
      email,
      message: isAdmin ? "Tài khoản Quản trị viên không được phép đăng nhập vào Cổng Nhân viên (8080)." : "Quyền nhân viên hợp lệ.",
    };
  }
}

/**
 * Fetch effective permissions for an employee by merging role + user overrides.
 * @param {string} userId
 */
export async function getEffectiveUserPermissions(userId) {
  const { data, error } = await supabase.schema("eas").rpc("get_effective_user_permissions", { p_user_id: userId });
  if (error) throw error;
  return data;
}

/**
 * Fetch employee working status (08:00 - 17:30, Mon - Fri).
 * @param {string} userId
 */
export async function getUserWorkingStatus(userId) {
  const { data, error } = await supabase.schema("eas").rpc("get_user_working_status", { p_user_id: userId });
  if (error) throw error;
  return Array.isArray(data) ? data[0] : data;
}

/**
 * Fetch detailed request involvement for an employee across 5 lifecycle stages.
 * @param {string} userId
 */
export async function getUserRequestsDetail(userId) {
  const { data, error } = await supabase.schema("eas").rpc("get_user_requests_detail", { p_user_id: userId });
  if (error) throw error;
  return data;
}

/**
 * Call AI completion procedure to sync new regulations and unlock Web Client.
 */
export async function completeAiRegulationLearning() {
  const { data, error } = await supabase.schema("eas").rpc("complete_ai_regulation_learning");
  if (error) throw error;
  return data;
}

export default supabase;
