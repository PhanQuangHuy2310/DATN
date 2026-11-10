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
// Keep dropdowns warm but don't delay remote admin changes for minutes.
const STATIC_CACHE_TTL_MS = 90 * 1000;
// Query strings, pagination and filters can otherwise grow this map forever.
const MAX_CACHED_RESOURCES = 120;
function storeResource(path, data) {
  // Reinserting a key keeps recent pages hot (small bounded LRU cache).
  cached.delete(path);
  cached.set(path, { timestamp: Date.now(), data });
  while (cached.size > MAX_CACHED_RESOURCES) {
    cached.delete(cached.keys().next().value);
  }
}
function resourceTtl(path) {
  return /^\/api\/v1\/(?:meta\/departments|request-types(?:\?|$)|meta\/request-types(?:\?|$))/.test(path)
    ? STATIC_CACHE_TTL_MS : CACHE_TTL_MS;
}
let generation = 0;

// One disconnected Supabase/API must not trigger a page-wide GET stampede.
// This is a transport gate, not an authorization or workflow bypass.
const MAX_PARALLEL_READS = 5;
let activeReads = 0;
const readWaiters = [];
// Adaptive pacing limits bursts without refusing future reads while the DB
// has already recovered. A failed widget must not keep all pages offline.
const backendOutage = { failures: 0, retryAt: 0 };
// The Django per-IP limiter is shared by all pages. Never send another burst
// when it responds RATE_LIMIT_EXCEEDED; respect its Retry-After instead.
let rateLimitUntil = 0;
function remainingRateLimitMs() {
  return Math.max(0, rateLimitUntil - Date.now());
}
function rateLimitError() {
  const error = new Error("RATE_LIMIT_EXCEEDED");
  error.status = 429;
  error.retryAfterMs = remainingRateLimitMs();
  return error;
}

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
  backendOutage.failures = Math.min(4, backendOutage.failures + 1);
  backendOutage.retryAt = Date.now() + Math.min(4000, 500 * 2 ** (backendOutage.failures - 1));
}

function isRetryableStatus(error) {
  return sharedOutage(error) && [502, 503, 504].includes(error?.status);
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
export async function api(path, { silent = false, toast = true, timeoutMs, forceProbe = false, ...options } = {}) {
  const method = (options.method || "GET").toUpperCase();
  const isRead = method === "GET" || method === "HEAD";
<<<<<<< HEAD
  // Health checks must always be callable while the regular API is recovering.
  const isDiagnostic = HEALTH_PATH.test(path);
  // Keep auth and health probes responsive even when five slow data widgets
  // are already running. All other reads remain bounded by the semaphore.
  const priority = isDiagnostic || /^\/api\/v1\/auth\/(me|csrf)$/.test(path);
  const release = isRead && !priority ? await readPermit() : () => {};
  try {
    // Preserve /health/* probes during an API rate limit, but do not send
    // more auth/AI/data requests to Django until its Retry-After expires.
    if (!isDiagnostic && remainingRateLimitMs() > 0) throw rateLimitError();
    // A short shared pause replaces the old hard-fail 60-second circuit.
    // Every new request still gets a real attempt; success resets the backoff.
    if (isRead && !isDiagnostic && !forceProbe && backendOutage.retryAt > Date.now()) {
      await pause(Math.min(backendOutage.retryAt - Date.now(), 4000));
    }
    const headers = new Headers(options.headers || {});
    if (!(options.body instanceof FormData) && options.body !== undefined) headers.set("Content-Type", "application/json");
    if (!isRead && method !== "OPTIONS") {
      const token = cookie("csrftoken");
      if (token) headers.set("X-CSRFToken", decodeURIComponent(token));
    }
    // A DB-down response is retried at most once. Never retry a mutation.
    // Readiness returns structured 503 diagnostics, so never retry that probe.
    const attempts = isRead && !isDiagnostic ? 2 : 1;
    const deadline = Date.now() + (timeoutMs ?? (isRead ? 40000 : 45000));
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      const controller = new AbortController();
      let timedOut = false;
      // A single read is allowed time for a slow Supabase query, but all
      // attempts share a total deadline (no 30s * N runaway spinner).
      const remaining = Math.max(1, deadline - Date.now());
      const attemptBudget = isRead ? Math.min(30000, remaining) : remaining;
      const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, attemptBudget);
      const onAbort = () => controller.abort();
      options.signal?.addEventListener("abort", onAbort, { once: true });
      if (options.signal?.aborted) controller.abort();
      try {
        if (!isDiagnostic && remainingRateLimitMs() > 0) throw rateLimitError();
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
          const retryAfter = Number(response.headers.get("Retry-After"));
          if (Number.isFinite(retryAfter) && retryAfter > 0) error.retryAfterMs = Math.min(300000, retryAfter * 1000);
          if (response.status === 429 && code === "RATE_LIMIT_EXCEEDED") {
            error.retryAfterMs ||= 60000;
            rateLimitUntil = Math.max(rateLimitUntil, Date.now() + error.retryAfterMs);
          }
          if (isRead && isRetryableStatus(error) && attempt < attempts - 1 && deadline - Date.now() > 1000) {
            await pause(350 + Math.floor(Math.random() * 200));
            continue;
          }
          throw error;
        }
        if (!isRead && !silent && body?.success === false) {
          const error = new Error(body?.error?.code || "OPERATION_NOT_CONFIRMED");
          error.status = response.status;
          error.responseBody = body;
          error.serverMessage = body?.error?.message || body?.message || "";
          throw error;
        }
        if (body === null) {
          const error = new Error("INVALID_RESPONSE");
          error.status = response.status;
          throw error;
        }
        // A successful application/health request shows that the API recovered.
        if (isRead && !isDiagnostic && path !== "/api/v1/auth/csrf") {
          backendOutage.failures = 0;
          backendOutage.retryAt = 0;
        }
        if (!isRead && method !== "OPTIONS") {
          if (path === "/api/v1/auth/login" || path === "/api/v1/auth/logout") {
            invalidateResources();
          } else if (!silent && !path.includes("/ai/")) {
            invalidateResources();
          }
          if (!silent && toast && !path.includes("/ai/")) notify(mutationMessage(path));
        }
        return body;
      } catch (error) {
        if (options.signal?.aborted) throw error;
        const transportError = error.name === "AbortError" || error instanceof TypeError;
        if (isRead && transportError && attempt < attempts - 1 && deadline - Date.now() > 1000) {
          await pause(350 + Math.floor(Math.random() * 200));
=======
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
>>>>>>> origin/main
          continue;
        }
        if (isRead && !isDiagnostic && sharedOutage(error)) markOutage();
        if (!isRead && !silent && toast) notify(timedOut ? "Yêu cầu quá thời gian phản hồi. Kiểm tra trạng thái trước khi thử lại." : "Không thể thực hiện thao tác. Kiểm tra thông tin và thử lại.", "error");
        if (transportError) {
          const failure = new Error(timedOut || error.name === "AbortError"
            ? (isRead ? "REQUEST_TIMED_OUT" : "REQUEST_TIMEOUT_UNKNOWN")
            : "NETWORK_UNAVAILABLE");
          failure.status = 0;
          throw failure;
        }
        throw error;
      } finally {
        clearTimeout(timeout);
        options.signal?.removeEventListener("abort", onAbort);
      }
<<<<<<< HEAD
=======
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
>>>>>>> origin/main
    }
  } finally {
    release();
  }
}

export function getResource(path) {
  const previous = cached.get(path);
  if (previous && Date.now() - previous.timestamp < resourceTtl(path)) return Promise.resolve(previous.data);
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
    if (generation === currentGeneration) storeResource(path, result);
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
// One CSRF cookie is sufficient for the browser session. Avoid requesting a
// new one on every login attempt, tab focus or simultaneous session bootstrap.
let csrfInitialization = null;
export async function initializeCsrf(options = {}) {
  if (cookie("csrftoken")) return { status: "ok" };
  if (csrfInitialization) return csrfInitialization;
  const pending = api("/api/v1/auth/csrf", options);
  csrfInitialization = pending;
  try { return await pending; }
  finally { if (csrfInitialization === pending) csrfInitialization = null; }
}
export function idempotencyKey() { return crypto.randomUUID(); }
