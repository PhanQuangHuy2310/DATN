export const API_BASE = (import.meta.env?.VITE_API_BASE_URL || "").replace(
  /\/$/,
  "",
);

function cookie(name) {
  return document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`))
    ?.split("=")
    .slice(1)
    .join("=");
}

// A short outage of the Supabase pooler must not cause a storm of overlapping
// requests. Retry *only reads*, once; mutations (including login / approvals)
// must never be replayed by the HTTP client.
export function retryDelayMs(response) {
  const raw = response.headers.get("Retry-After");
  const seconds = raw === null ? NaN : Number(raw);
  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.min(4000, seconds * 1000);
  }
  return 500; // Fast fallback for an unlabelled gateway outage.
}

function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason || new DOMException("Aborted", "AbortError"));
      return;
    }
    const abort = () => {
      clearTimeout(timer);
      reject(signal.reason || new DOMException("Aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", abort, { once: true });
  });
}

export async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = cookie("csrftoken");
    if (token) headers.set("X-CSRFToken", decodeURIComponent(token));
  }
  const readOnly = method === "GET" || method === "HEAD";
  let response;
  let body;
  for (let attempt = 0; ; attempt += 1) {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      method,
      headers,
      credentials: "same-origin",
    });
    const isJson = (response.headers.get("content-type") || "").includes("application/json");
    body = isJson ? await response.json().catch(() => null) : null;
    const transient = [502, 503, 504].includes(response.status);
    if (!(readOnly && attempt === 0 && transient)) break;
    await sleep(retryDelayMs(response), options.signal);
  }

  // A failed Django request can return HTML (for example, a debug 500 page).
  // Report the actual HTTP failure instead of presenting it as INVALID_RESPONSE.
  if (!response.ok) {
    const code = body?.error?.code || (response.status >= 500 ? "SERVER_ERROR" : `HTTP_${response.status}`);
    const error = new Error(code);
    error.status = response.status;
    error.fields = body?.error?.fields;
    error.correlationId = body?.correlation_id || response.headers.get("X-Correlation-ID") || "";
    throw error;
  }
  if (body === null) {
    const error = new Error("INVALID_RESPONSE");
    error.status = response.status;
    throw error;
  }
  return body;
}

export async function initializeCsrf() {
  return api("/api/v1/auth/csrf");
}

export function idempotencyKey() {
  return crypto.randomUUID();
}
