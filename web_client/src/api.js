export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const DATA_EVENT = "eas:data-changed";
const TOAST_EVENT = "eas:toast";
// L11: an expired session (401 on a business endpoint) sends the user to login.
export const SESSION_EXPIRED_EVENT = "eas:session-expired";
// Auth endpoints report errors inline on their own forms (L5).
const isAuthPath = (path) => path.includes("/api/v1/auth/");
const inFlight = new Map();
const cached = new Map();
const CACHE_TTL_MS = 20000;
let generation = 0;

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
export async function api(path, { silent = false, timeoutMs, ...options } = {}) {
  const method = (options.method || "GET").toUpperCase();
  const isRead = method === "GET" || method === "HEAD";
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && options.body !== undefined) headers.set("Content-Type", "application/json");
  if (!isRead && method !== "OPTIONS") {
    const token = cookie("csrftoken");
    if (token) headers.set("X-CSRFToken", decodeURIComponent(token));
  }
  // Only replay safe, idempotent reads. Never retry a non-idempotent command.
  const attempts = isRead ? 2 : 1;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const waitMs = timeoutMs || (isRead ? 15000 : 30000);
    const timeoutSignal = typeof AbortSignal !== "undefined" && AbortSignal.timeout
      ? AbortSignal.timeout(waitMs)
      : null;
    const controller = new AbortController();
    // Writes may still be committing to Supabase: wait longer and never retry them.
    const timeout = timeoutSignal ? null : setTimeout(() => controller.abort(), waitMs);
    const onAbort = () => controller.abort();
    timeoutSignal?.addEventListener("abort", onAbort, { once: true });
    options.signal?.addEventListener("abort", onAbort, { once: true });
    if (options.signal?.aborted || timeoutSignal?.aborted) controller.abort();
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...options, method, headers, credentials: "include", signal: timeoutSignal && !options.signal ? timeoutSignal : controller.signal,
      });
      const isJson = (response.headers.get("content-type") || "").includes("application/json");
      const body = isJson ? await response.json().catch(() => null) : null;
      if (!response.ok) {
        const code = body?.error?.code || (response.status >= 500 ? "SERVER_ERROR" : `HTTP_${response.status}`);
        const error = new Error(code);
        error.status = response.status;
        error.fields = body?.error?.fields;
        error.serverMessage = body?.error?.message || body?.message || "";
        error.correlationId = body?.correlation_id || response.headers.get("X-Correlation-ID") || "";
        if (response.status === 401 && !isAuthPath(path)) {
          window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
        }
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
      if (!isRead && method !== "OPTIONS" && !silent && !path.includes("/ai/")) {
        notify(mutationMessage(path));
        invalidateResources();
      }
      return body;
    } catch (error) {
      if (options.signal?.aborted) throw error;
      const isTimeoutAbort = error.name === "AbortError" || error.name === "TimeoutError";
      if (isRead && attempt < attempts - 1 && (isTimeoutAbort || error instanceof TypeError)) {
        await pause(300 * (2 ** attempt));
        continue;
      }
      if (!isRead && !silent && !isAuthPath(path)) notify(isTimeoutAbort ? "Yêu cầu quá thời gian phản hồi. Kiểm tra trạng thái trước khi thử lại." : "Không thể thực hiện thao tác. Kiểm tra thông tin và thử lại.", "error");
      if (!isRead && isTimeoutAbort) {
        // The server may have committed despite a client timeout. Do not retry.
        throw new Error("REQUEST_TIMEOUT_UNKNOWN");
      }
      throw error;
    } finally {
      if (timeout) clearTimeout(timeout);
      timeoutSignal?.removeEventListener("abort", onAbort);
      options.signal?.removeEventListener("abort", onAbort);
    }
  }
}

export function getResource(path) {
  const previous = cached.get(path);
  if (previous && Date.now() - previous.timestamp < CACHE_TTL_MS) return Promise.resolve(previous.data);
  if (inFlight.has(path)) return inFlight.get(path);
  const currentGeneration = generation;
  const request = api(path).then((result) => {
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
export async function initializeCsrf() { return api("/api/v1/auth/csrf"); }
export function idempotencyKey() { return crypto.randomUUID(); }
