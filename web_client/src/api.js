export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(
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

export async function api(path, options = {}) {
  const method = options.method || "GET";
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = cookie("csrftoken");
    if (token) headers.set("X-CSRFToken", decodeURIComponent(token));
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });
  // A failed Django request can return HTML (for example, a debug 500 page).
  // Report the actual HTTP failure instead of presenting it as INVALID_RESPONSE.
  const isJson = (response.headers.get("content-type") || "").includes("application/json");
  const body = isJson ? await response.json().catch(() => null) : null;
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
