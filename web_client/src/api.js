export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const DATA_EVENT = "eas:data-changed";
const TOAST_EVENT = "eas:toast";
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
  if (path.includes("/auth/logout")) return "Đã đăng xuất an toàn";
  if (path.includes("/attachments")) return "Tài liệu đã được cập nhật";
  if (path.includes("/approval")) return "Đã ghi nhận quyết định phê duyệt";
  if (path.includes("/acceptance")) return "Đã ghi nhận kết quả nghiệm thu";
  if (path.includes("/execution")) return "Đã cập nhật công việc";
  return "Thao tác đã thực hiện thành công";
}

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function api(path, options = {}) {
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
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 9000);
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
        error.fields = body?.error?.fields;
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
      if (!isRead && method !== "OPTIONS") {
        if (!path.includes("/ai/")) notify(mutationMessage(path));
        if (!path.includes("/ai/")) invalidateResources();
      }
      return body;
    } catch (error) {
      if (options.signal?.aborted) throw error;
      if (isRead && attempt < attempts - 1 && (error.name === "AbortError" || error instanceof TypeError)) {
        await pause(300 * (2 ** attempt));
        continue;
      }
      if (!isRead) notify(error.name === "AbortError" ? "Yêu cầu quá thời gian phản hồi. Kiểm tra trạng thái trước khi thử lại." : "Không thể thực hiện thao tác. Kiểm tra thông tin và thử lại.", "error");
      if (!isRead && error.name === "AbortError") {
        // The server may have committed despite a client timeout. Do not retry.
        throw new Error("REQUEST_TIMEOUT_UNKNOWN");
      }
      throw error;
    } finally {
      clearTimeout(timeout);
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
