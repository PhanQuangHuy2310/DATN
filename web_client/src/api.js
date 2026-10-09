const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

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
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = cookie("csrftoken");
    if (token) headers.set("X-CSRFToken", decodeURIComponent(token));
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
  });
  const body = await response.json().catch(() => ({ error: { code: "INVALID_RESPONSE" } }));
  if (!response.ok) {
    const error = new Error(body.error?.code || `HTTP_${response.status}`);
    error.status = response.status;
    error.fields = body.error?.fields;
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
