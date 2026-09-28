import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient, envelopeMessage, get } from "./client";
import { useToast } from "../ui";
import { isTerminalJobStatus } from "../format";

export interface UploadResponse {
  job_id: string;
  status: string;
  document_id: string | null;
  version_id: string | null;
  duplicate_match: boolean;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  trace_id: string;
  warnings: string[];
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  attempt: number;
  error_code: string | null;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  uploader_id: string;
  trace_id: string;
  created_at: string;
  updated_at: string;
}

/**
 * Build an idempotency key for one upload attempt.
 *
 * The key is generated at runtime (never hard-coded) and kept in the caller's
 * state so a retry of the *same* file reuses it instead of re-ingesting content.
 */
export function newIdempotencyKey(): string {
  const cryptoObject = globalThis.crypto;
  if (cryptoObject && typeof cryptoObject.randomUUID === "function") {
    return cryptoObject.randomUUID();
  }
  return `idem-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export interface UploadInput {
  file: File;
  idempotencyKey: string;
  source?: string;
}

/**
 * Upload a document as a raw body with `filename` and `Idempotency-Key` metadata,
 * matching the transport documented in docs/11 section 3.
 */
export function useUploadDocument() {
  const toast = useToast();
  return useMutation({
    mutationFn: async ({ file, idempotencyKey, source }: UploadInput) => {
      const response = await apiClient.post<UploadResponse>("/documents/upload", file, {
        params: { filename: file.name, ...(source ? { source } : {}) },
        headers: {
          "Content-Type": file.type || "application/octet-stream",
          "Idempotency-Key": idempotencyKey,
        },
        timeout: 120_000,
      });
      return response.data;
    },
    onError: (error: unknown) => toast(envelopeMessage(error), "error"),
  });
}

/** Poll an ingestion job until it reaches a terminal state. */
export function useJobStatus(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => get<JobStatusResponse>(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) => (isTerminalJobStatus(query.state.data?.status) ? false : 3_000),
  });
}
