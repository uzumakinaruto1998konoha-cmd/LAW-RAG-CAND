import { useQuery } from "@tanstack/react-query";
import { get } from "./client";

export interface HealthResponse {
  status: string;
  phase: string;
  architecture_version: string;
}

export interface ReadinessCheck {
  name: string;
  status: "ok" | "degraded";
  detail: string | null;
}

export interface ReadinessResponse {
  status: "ready" | "degraded";
  checks: ReadinessCheck[];
  indexed_chunk_count: number;
  indexed_version_count: number;
}

/** Liveness probe: no authentication is required (docs/11 section 3). */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => get<HealthResponse>("/health"),
    refetchInterval: 30_000,
  });
}

/** Readiness probe with subsystem checks and index sizes. */
export function useReadiness() {
  return useQuery({
    queryKey: ["ready"],
    queryFn: () => get<ReadinessResponse>("/ready"),
    refetchInterval: 30_000,
  });
}
