/** Typed API client: same-origin in production, Vite proxy in dev. */

const BASE = (import.meta as ImportMeta & { env: Record<string, string> }).env?.VITE_API_URL || "";
const PREFIX = `${BASE}/api/v1`;

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export function getToken(): string | null {
  return localStorage.getItem("idp_token");
}

async function request<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
    // Second channel: some hosting proxies consume the Authorization header,
    // so the same token is also offered on a custom header that passes through.
    headers["X-Access-Token"] = token;
  }
  if (init.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";

  // credentials: "include" sends the HttpOnly auth cookie (third channel).
  const resp = await fetch(`${PREFIX}${path}`, { ...init, headers, credentials: "include" });
  const text = await resp.text();

  // Session expired or invalid: drop stale credentials and bounce to login.
  if (resp.status === 401 && !path.startsWith("/auth/login")) {
    localStorage.removeItem("idp_token");
    localStorage.removeItem("idp_user");
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }
  let body: any = {};
  try { body = text ? JSON.parse(text) : {}; } catch { /* non-JSON */ }

  if (!resp.ok) {
    const err = body?.error ?? { code: "HTTP_" + resp.status, message: resp.statusText };
    throw new ApiError(resp.status, err.code, err.message);
  }
  if (body && typeof body === "object" && "success" in body) return body.data as T;
  return body as T;
}

export const api = {
  get: <T = any>(path: string) => request<T>(path),
  post: <T = any>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: data === undefined ? undefined : JSON.stringify(data) }),
  put: <T = any>(path: string, data: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(data) }),
  delete: <T = any>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T = any>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
};
