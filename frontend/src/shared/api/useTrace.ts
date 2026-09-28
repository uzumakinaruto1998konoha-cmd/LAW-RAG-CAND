import { useQuery } from "@tanstack/react-query";
import { get } from "./client";

export interface TraceResult {
  rank: number;
  chunk_id: string;
  score: number;
  retrieval_method: string;
}

export interface TraceResponse {
  trace_id: string;
  user_id: string;
  query: string;
  query_type: string;
  as_of_date: string | null;
  filters: Record<string, string> | null;
  manifest_id: string | null;
  result_count: number;
  latency_ms: number | null;
  created_at: string;
  results: TraceResult[];
}

/**
 * Read a retrieval trace (trace owner or `audit.view`; others get 404).
 * Traces carry chunk identifiers only, never document content (docs/11 section 3).
 */
export function useTrace(traceId: string | null) {
  return useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => get<TraceResponse>(`/traces/${traceId}`),
    enabled: !!traceId,
  });
}
