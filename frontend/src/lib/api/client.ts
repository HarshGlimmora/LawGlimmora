import axios, { AxiosError, AxiosInstance } from "axios";

import { log } from "@/lib/logger";

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;

  constructor(status: number, body: ApiErrorBody["error"] | undefined, fallback: string) {
    super(body?.message || fallback);
    this.status = status;
    this.code = body?.code || "unknown";
    this.details = body?.details;
  }
}

/**
 * Resolve the backend base URL.
 *
 * Order:
 *   1. NEXT_PUBLIC_API_BASE_URL                  (Vercel / prod)
 *   2. "http://localhost:8000"                   (dev fallback)
 *
 * In production builds (NODE_ENV === "production") we emit a console
 * warning when the env var is missing so the issue surfaces in browser
 * devtools immediately instead of failing silently with cross-origin
 * "Network Error" later.
 */
export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (raw && raw.length > 0) return raw.replace(/\/$/, "");
  if (process.env.NODE_ENV === "production" && typeof window !== "undefined") {
    log.warn(
      "api",
      "NEXT_PUBLIC_API_BASE_URL is not set — falling back to http://localhost:8000. " +
        "Set it in Vercel project settings before deploying.",
    );
  }
  return "http://localhost:8000";
}

const BASE_URL = getApiBaseUrl();

export const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  // Gemini 2.5 Pro can spend 30–90s on internal reasoning before emitting
  // text, and the evidence-ingest pipeline runs entity extraction over many
  // chunks. 5 min covers both without masking real hangs.
  timeout: 5 * 60_000,
});

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError<ApiErrorBody>) => {
    const status = err.response?.status ?? 0;
    const body = err.response?.data?.error;
    const code = body?.code ?? (status === 0 ? "network" : "unknown");
    log.error("api", `${err.config?.method?.toUpperCase() ?? "?"} ${err.config?.url} → ${status} ${code}`, body);
    throw new ApiError(status, body, err.message);
  },
);

/**
 * Build an absolute backend URL for direct browser navigation (file
 * downloads, exports). Uses the module-level BASE_URL so the missing-env
 * warning only fires once on import, not on every call.
 */
export function backendUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${BASE_URL}${p}`;
}
