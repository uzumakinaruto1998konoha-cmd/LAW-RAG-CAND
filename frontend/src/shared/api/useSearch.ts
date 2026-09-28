import { useMutation } from "@tanstack/react-query";
import { post, envelopeMessage } from "./client";
import { useToast } from "../ui";

export interface SearchResult {
  rank: number;
  chunk_id: string;
  version_id: string;
  document_id: string;
  document_number: string;
  document_title: string;
  issuing_body: string;
  structural_path: string;
  heading: string | null;
  snippet: string;
  page_start: number | null;
  page_end: number | null;
  score: number;
  validity_status: string;
  is_verified: boolean;
}

export interface SearchRequest {
  query: string;
  as_of_date?: string;
  filters?: Record<string, string>;
  top_k?: number;
  query_type?: "hybrid" | "lexical" | "semantic";
}

export interface SearchResponse {
  query: string;
  trace_id: string;
  query_type: string;
  as_of_date?: string | null;
  result_count: number;
  latency_ms?: number | null;
  results: SearchResult[];
  warnings: string[];
}

export function useSearch() {
  const toast = useToast();
  return useMutation({
    mutationFn: (payload: SearchRequest) => post<SearchResponse>("/search", payload),
    onError: (err: unknown) => toast(envelopeMessage(err), "error"),
  });
}