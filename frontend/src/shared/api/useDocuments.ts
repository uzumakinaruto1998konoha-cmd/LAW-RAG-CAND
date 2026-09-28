import { useQuery } from "@tanstack/react-query";
import { get } from "./client";

export interface DocumentSummary {
  document_id: string;
  version_id: string;
  document_number: string;
  title: string;
  issuing_body: string;
  document_type: string;
  issue_date: string;
  effective_date: string | null;
  expiry_date: string | null;
  validity_status: string;
  is_verified: boolean;
  collection_ids: string[];
  chunk_count: number;
}

export interface ChunkModel {
  chunk_id: string;
  chunk_index: number;
  structural_path: string;
  heading: string | null;
  node_kind: string | null;
  page_start: number | null;
  page_end: number | null;
  content: string;
  token_count: number | null;
}

export interface DocumentDetailResponse {
  document: DocumentSummary;
  chunks: ChunkModel[];
}

export interface DocumentListResponse {
  count: number;
  documents: DocumentSummary[];
}

/**
 * Read the ACL-filtered knowledge base.
 *
 * Errors are surfaced by the pages with `ErrorState` + `envelopeMessage`, so the
 * hooks stay free of side effects (react-query v5 removed `onError` for queries).
 */
export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: () => get<DocumentListResponse>("/documents"),
  });
}

export function useDocument(id: string | null) {
  return useQuery({
    queryKey: ["document", id],
    queryFn: () => get<DocumentDetailResponse>(`/documents/${id}`),
    enabled: !!id,
  });
}
