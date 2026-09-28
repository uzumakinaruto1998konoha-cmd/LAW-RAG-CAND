import axios, { AxiosInstance, AxiosRequestConfig } from "axios";

const API_BASE = "/api/v1";

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("law_rag_token");
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("law_rag_token");
      window.location.href = "/dev/login";
    }
    return Promise.reject(err);
  }
);

export function request<T>(config: AxiosRequestConfig): Promise<T> {
  return apiClient.request<T>(config).then((r) => r.data);
}

export function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return request<T>({ method: "GET", url, ...config });
}

export function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return request<T>({ method: "POST", url, data, ...config });
}

export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id: string;
    field_errors?: { field: string; message: string; code: string }[];
  };
}

/** Shape the API promises on failure: `{ error: { message, field_errors } }` (docs/11 §4). */
interface ErrorEnvelopeShape {
  message?: string;
  response?: { data?: { error?: Partial<ErrorEnvelope["error"]> } };
}

function asErrorShape(err: unknown): ErrorEnvelopeShape {
  return (typeof err === "object" && err !== null ? err : {}) as ErrorEnvelopeShape;
}

/** Human-readable message for any transport or envelope failure. */
export function envelopeMessage(err: unknown): string {
  const shaped = asErrorShape(err);
  return shaped.response?.data?.error?.message || shaped.message || "Đã có lỗi xảy ra";
}

/** Field-level validation errors reported by the server, if any. */
export function envelopeFieldErrors(
  err: unknown
): { field: string; message: string; code: string }[] {
  return asErrorShape(err).response?.data?.error?.field_errors ?? [];
}