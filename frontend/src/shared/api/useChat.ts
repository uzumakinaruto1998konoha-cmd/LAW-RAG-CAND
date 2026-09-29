import { useMutation, useQuery } from "@tanstack/react-query";
import { get, post, envelopeMessage } from "./client";
import { useToast } from "../ui";

export interface EvidenceModel {
  evidence_id: string;
  chunk_id: string;
  version_id: string;
  document_number: string | null;
  document_title: string;
  structural_path: string;
  excerpt: string;
  page_start: number | null;
  page_end: number | null;
  score: number;
  is_verified: boolean;
  validity_status: string;
}

export interface CitationModel {
  citation_id: string;
  message_id: string;
  evidence_id: string;
  chunk_id: string;
  version_id: string;
  document_number: string | null;
  document_title: string;
  issuing_body: string | null;
  structural_path: string;
  excerpt: string;
  page_start: number | null;
  page_end: number | null;
  viewer_url: string | null;
  validity_status: string;
  as_of_date: string | null;
  status: string;
}

export interface ChatRequest {
  question: string;
  as_of_date?: string;
  filters?: Record<string, string>;
  conversation_id?: string;
  top_k?: number;
  query_type?: "hybrid" | "lexical" | "semantic";
}

export interface ChatResponse {
  message_id: string;
  conversation_id: string;
  answer: string;
  insufficient_evidence: boolean;
  as_of_date: string | null;
  citations: CitationModel[];
  evidence: EvidenceModel[];
  warnings: string[];
  trace_id: string;
}

export function useChat() {
  const toast = useToast();
  return useMutation({
    mutationFn: (payload: ChatRequest) => post<ChatResponse>("/chat", payload),
    onError: (err: unknown) => toast(envelopeMessage(err), "error"),
  });
}

export interface ConversationModel {
  conversation_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

export interface MessageModel {
  message_id: string;
  conversation_id: string;
  role: string;
  content: string;
  trace_id: string | null;
  as_of_date: string | null;
  insufficient_evidence: boolean;
  created_at: string;
}

export interface ConversationDetailResponse {
  conversation: ConversationModel;
  messages: MessageModel[];
}

export interface ConversationListResponse {
  count: number;
  limit: number;
  offset: number;
  conversations: ConversationModel[];
}

export function useCreateConversation() {
  return useMutation({
    mutationFn: (payload: { title?: string | null }) =>
      post<ConversationModel>("/conversations", payload ?? {}),
  });
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: ["conversation", id],
    queryFn: () => get<ConversationDetailResponse>(`/conversations/${id}`),
    enabled: !!id,
  });
}

export function useConversations(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["conversations", limit, offset],
    queryFn: () => get<ConversationListResponse>(`/conversations?limit=${limit}&offset=${offset}`),
  });
}