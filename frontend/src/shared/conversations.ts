/**
 * Client-side registry of conversations opened in this browser.
 *
 * The `/api/v1` contract exposes conversation create/read only, so there is no
 * server-side listing endpoint yet (docs/11 section 2 keeps pagination and the
 * remaining conversation endpoints TBD). Until that exists, the conversations
 * page reads this browser-local index and re-fetches each conversation through
 * the authorized `GET /conversations/{id}` endpoint, which enforces ACL again.
 *
 * Only opaque identifiers and titles are stored: no answers or legal content.
 */

export const CONVERSATIONS_STORAGE_KEY = "law_rag_conversations";

export interface StoredConversation {
  conversation_id: string;
  title: string | null;
  updated_at: string;
}

const MAX_ENTRIES = 50;

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

function isStoredConversation(value: unknown): value is StoredConversation {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<StoredConversation>;
  return (
    typeof candidate.conversation_id === "string" &&
    candidate.conversation_id.length > 0 &&
    (candidate.title === null || typeof candidate.title === "string") &&
    typeof candidate.updated_at === "string"
  );
}

export function listStoredConversations(): StoredConversation[] {
  const raw = storage()?.getItem(CONVERSATIONS_STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isStoredConversation);
  } catch {
    return [];
  }
}

/** Insert or move a conversation to the front of the local index. */
export function rememberConversation(entry: StoredConversation): StoredConversation[] {
  const next = [entry, ...listStoredConversations().filter((item) => item.conversation_id !== entry.conversation_id)].slice(
    0,
    MAX_ENTRIES
  );
  try {
    storage()?.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage may be unavailable (private mode, quota); the UI still works.
  }
  return next;
}

export function forgetConversation(conversationId: string): StoredConversation[] {
  const next = listStoredConversations().filter((item) => item.conversation_id !== conversationId);
  try {
    storage()?.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Ignore storage failures: forgetting locally is best effort.
  }
  return next;
}
