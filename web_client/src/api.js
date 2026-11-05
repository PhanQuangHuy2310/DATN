export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const DATA_EVENT = "eas:data-changed";
const TOAST_EVENT = "eas:toast";
const inFlight = new Map();
const cached = new Map();
const CACHE_TTL_MS = 20000;
let generation = 0;

// One disconnected Supabase/API must not trigger a page-wide GET stampede.
// This is a transport gate, not an authorization or workflow bypass.
const MAX_PARALLEL_READS = 5;
let activeReads = 0;
const readWaiters = [];
const backendOutage = { failures: 0, retryAt: 0 };
const HEALTH_PATH = /^\/health\//;

function readPermit() {
  return new Promise((resolve) => {
    const enter = () => {
      activeReads += 1;
      resolve(() => {
        activeReads -= 1;
        readWaiters.shift()?.();
      });
    };
    if (activeReads < MAX_PARALLEL_READS) enter();
    else readWaiters.push(enter);
  });
}

function sharedOutage(error) {
  if (error?.name === "AbortError" || error instanceof TypeError) return true;
  if (![502, 503, 504].includes(error?.status)) return false;
  // A single missing AI feature returning 503 is NOT a global DB outage.
  const code = error?.message || "";
  return !error.responseBody || [
    "DATABASE_TEMPORARILY_UNAVAILABLE", "BACKEND_UNAVAILABLE",
    "SERVICE_UNAVAILABLE", "SERVER_ERROR",
  ].includes(code);
}

function markOutage() {
  backendOutage.failures = Math.min(5, backendOutage.failures + 1);
  backendOutage.retryAt = Date.now() + Math.min(60000, 4000 * 2 ** (backendOutage.failures - 1));
}

function unavailableDuringCooldown() {
  const error = new Error("BACKEND_TEMPORARILY_UNAVAILABLE");
  error.status = 503;
  error.retryAfterMs = Math.max(0, backendOutage.retryAt - Date.now());
  return error;
}

export function invalidateResources() {
  generation += 1;
  cached.clear();
  inFlight.clear();
  window.dispatchEvent(new Event(DATA_EVENT));
}

export function notify(message, type = "success") {
  window.dispatchEvent(new CustomEvent(TOAST_EVENT, { detail: { message, type } }));
}

function cookie(name) {
  return document.cookie.split(";").map((part) => part.trim())
    .find((item) => item.startsWith(`${name}=`))?.slice(name.length + 1);
}

function mutationMessage(path) {
  if (path.includes("/auth/login")) return "Đăng nhập thành công";
  if (path.includes("/attachments")) return "Tài liệu đã được cập nhật";
  if (path.includes("/reassign")) return "Đã điều chuyển người xử lý";
  if (path.includes("/replay")) return "Đã đưa thông báo vào hàng gửi lại";
  if (path.includes("/maintenance/start")) return "Đã bật chế độ bảo trì";
  if (path.includes("/maintenance/complete")) return "Đã kết thúc bảo trì";
  if (path.includes("/cancel")) return "Đã hủy yêu cầu";
  if (path.includes("requests/submit") || /requests\/[^/]+\/submit$/.test(path)) return "Đã gửi yêu cầu phê duyệt";
  if (path.includes("/request-drafts")) return "Đã lưu bản nháp";
  if (path.includes("/issues")) return "Đã ghi nhận vướng mắc";
  if (path.includes("/auth/logout")) return "Đã đăng xuất an toàn";
  if (path.includes("/approval")) return "Đã ghi nhận quyết định phê duyệt";
  if (path.includes("/acceptance")) return "Đã ghi nhận kết quả nghiệm thu";
  if (path.includes("/execution")) return "Đã cập nhật công việc";
  return "Thao tác đã thực hiện thành công";
}

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** `silent`: a read-only POST (preview) or a call whose caller refreshes its own
 * view; skip the generic toast and global cache invalidation.
 * `timeoutMs`: override the default wait for long server-side work. */
export async function api(path, { silent = false, timeoutMs, forceProbe = false, ...options } = {}) {
  const method = (options.method || "GET").toUpperCase();
  const isRead = method === "GET" || method === "HEAD";
  // Health checks must always be callable while the regular API is recovering.
  const isDiagnostic = HEALTH_PATH.test(path);
  const release = isRead ? await readPermit() : () => {};
  try {
    if (isRead && !isDiagnostic && !forceProbe && Date.now() < backendOutage.retryAt) {
      throw unavailableDuringCooldown();
    }
    const headers = new Headers(options.headers || {});
    if (!(options.body instanceof FormData) && options.body !== undefined) headers.set("Content-Type", "application/json");
    if (!isRead && method !== "OPTIONS") {
      const token = cookie("csrftoken");
      if (token) headers.set("X-CSRFToken", decodeURIComponent(token));
    }
    // A DB-down response is retried at most once. Never retry a mutation.
    // Readiness returns structured 503 diagnostics, so never retry that probe.
    const attempts = isRead && path !== "/health/ready" ? 2 : 1;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), timeoutMs || (isRead ? 15000 : 30000));
      const onAbort = () => controller.abort();
      options.signal?.addEventListener("abort", onAbort, { once: true });
      if (options.signal?.aborted) controller.abort();
      try {
        const response = await fetch(`${API_BASE}${path}`, {
          ...options, method, headers, credentials: "include", signal: controller.signal,
        });
        const isJson = (response.headers.get("content-type") || "").includes("application/json");
        const body = isJson ? await response.json().catch(() => null) : null;
        if (!response.ok) {
          const code = body?.error?.code || (response.status >= 500 ? "SERVER_ERROR" : `HTTP_${response.status}`);
          const error = new Error(code);
          error.status = response.status;
          error.responseBody = body;
          error.fields = body?.error?.fields;
          error.serverMessage = body?.error?.message || body?.message || "";
          error.correlationId = body?.correlation_id || response.headers.get("X-Correlation-ID") || "";
          if (isRead && [502, 503, 504].includes(response.status) && attempt < attempts - 1) {
            await pause(300 * (2 ** attempt));
            continue;
          }
          throw error;
        }
        if (body === null) {
          const error = new Error("INVALID_RESPONSE");
          error.status = response.status;
          throw error;
        }
        // A successful application/health request shows that the API recovered.
        if (isRead) {
          backendOutage.failures = 0;
          backendOutage.retryAt = 0;
        }
        if (!isRead && method !== "OPTIONS" && !silent && !path.includes("/ai/")) {
          notify(mutationMessage(path));
          invalidateResources();
        }
        return body;
      } catch (error) {
        if (options.signal?.aborted) throw error;
        if (isRead && attempt < attempts - 1 && (error.name === "AbortError" || error instanceof TypeError)) {
          await pause(300 * (2 ** attempt));
          continue;
        }
        if (isRead && !isDiagnostic && sharedOutage(error)) markOutage();
        if (!isRead && !silent) notify(error.name === "AbortError" ? "Yêu cầu quá thời gian phản hồi. Kiểm tra trạng thái trước khi thử lại." : "Không thể thực hiện thao tác. Kiểm tra thông tin và thử lại.", "error");
        if (!isRead && error.name === "AbortError") {
          throw new Error("REQUEST_TIMEOUT_UNKNOWN");
        }
        throw error;
      } finally {
        clearTimeout(timeout);
        options.signal?.removeEventListener("abort", onAbort);
      }
    }
  } finally {
    release();
  }
}

export function getResource(path) {
  const previous = cached.get(path);
  if (previous && Date.now() - previous.timestamp < CACHE_TTL_MS) return Promise.resolve(previous.data);
  if (inFlight.has(path)) return inFlight.get(path);
  const currentGeneration = generation;
  const request = api(path).catch((error) => {
    // A readiness endpoint intentionally returns 503 for failed checks. Its
    // JSON body is diagnostic data, not a transport error, so keep it visible.
    if (path === "/health/ready" && error.status === 503
        && error.responseBody?.status === "not_ready"
        && error.responseBody.checks) {
      return error.responseBody;
    }
    throw error;
  }).then((result) => {
    if (generation === currentGeneration) cached.set(path, { timestamp: Date.now(), data: result });
    return result;
  }).finally(() => { if (inFlight.get(path) === request) inFlight.delete(path); });
  inFlight.set(path, request);
  return request;
}

export function invalidateResource(path) { generation += 1; cached.delete(path); inFlight.delete(path); }

export function peekResource(path) { return cached.get(path)?.data ?? null; }
export function onDataChanged(listener) {
  window.addEventListener(DATA_EVENT, listener);
  return () => window.removeEventListener(DATA_EVENT, listener);
}
export function onToast(listener) {
  window.addEventListener(TOAST_EVENT, listener);
  return () => window.removeEventListener(TOAST_EVENT, listener);
}
export async function initializeCsrf(options = {}) { return api("/api/v1/auth/csrf", options); }
export function idempotencyKey() { return crypto.randomUUID(); }
