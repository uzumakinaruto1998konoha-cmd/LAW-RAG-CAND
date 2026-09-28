import { beforeEach, describe, expect, it } from "vitest";
import {
  CONVERSATIONS_STORAGE_KEY,
  forgetConversation,
  listStoredConversations,
  rememberConversation,
} from "../conversations";

beforeEach(() => {
  window.localStorage.clear();
});

describe("conversation index", () => {
  it("returns an empty list when nothing was stored", () => {
    expect(listStoredConversations()).toEqual([]);
  });

  it("stores identifiers only and keeps the newest conversation first", () => {
    rememberConversation({ conversation_id: "conv_1", title: "Câu hỏi 1", updated_at: "2026-09-27T10:00:00Z" });
    rememberConversation({ conversation_id: "conv_2", title: "Câu hỏi 2", updated_at: "2026-09-27T11:00:00Z" });

    const stored = listStoredConversations();
    expect(stored.map((item) => item.conversation_id)).toEqual(["conv_2", "conv_1"]);
    expect(Object.keys(stored[0]).sort()).toEqual(["conversation_id", "title", "updated_at"]);
  });

  it("updates an existing conversation instead of duplicating it", () => {
    rememberConversation({ conversation_id: "conv_1", title: "Cũ", updated_at: "2026-09-27T10:00:00Z" });
    rememberConversation({ conversation_id: "conv_1", title: "Mới", updated_at: "2026-09-27T12:00:00Z" });

    const stored = listStoredConversations();
    expect(stored).toHaveLength(1);
    expect(stored[0].title).toBe("Mới");
  });

  it("forgets a conversation on request", () => {
    rememberConversation({ conversation_id: "conv_1", title: null, updated_at: "2026-09-27T10:00:00Z" });
    expect(forgetConversation("conv_1")).toEqual([]);
    expect(listStoredConversations()).toEqual([]);
  });

  it("ignores corrupted or unexpected payloads", () => {
    window.localStorage.setItem(CONVERSATIONS_STORAGE_KEY, "{not json");
    expect(listStoredConversations()).toEqual([]);

    window.localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify([{ id: "missing_fields" }]));
    expect(listStoredConversations()).toEqual([]);
  });
});
