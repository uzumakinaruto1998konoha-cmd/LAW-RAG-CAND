import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { envelopeMessage, get } from "../shared/api/client";
import { ConversationDetailResponse } from "../shared/api/useChat";
import { forgetConversation, listStoredConversations } from "../shared/conversations";
import { formatDateTime, truncate } from "../shared/format";
import {
  EmptyState,
  LoadingSpinner,
  PageHeader,
  Panel,
  Warnings,
  useToast,
} from "../shared/ui";

/**
 * Conversations seen by this browser.
 *
 * `/api/v1` currently exposes create + read only (docs/11 section 2 keeps the
 * listing endpoint TBD), so the page lists the locally remembered identifiers and
 * re-reads each conversation through the authorized endpoint — the server still
 * decides access, and conversations of other users stay invisible (404).
 */
export default function ConversationsPage() {
  const [entries, setEntries] = useState(() => listStoredConversations());
  const navigate = useNavigate();
  const toast = useToast();

  const results = useQueries({
    queries: entries.map((entry) => ({
      queryKey: ["conversation", entry.conversation_id],
      queryFn: () => get<ConversationDetailResponse>(`/conversations/${entry.conversation_id}`),
      retry: false,
    })),
  });

  const isLoading = results.some((result) => result.isLoading);

  function handleForget(conversationId: string) {
    setEntries(forgetConversation(conversationId));
    toast("Đã bỏ hội thoại khỏi danh sách trên trình duyệt này.", "info");
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <PageHeader
        title="Hội thoại"
        description="Danh sách hội thoại đã mở trên trình duyệt này; nội dung luôn được đọc lại qua API có kiểm tra quyền."
        actions={
          <Link
            to="/chat"
            className="rounded-lg bg-brand-600 text-white px-3 py-2 text-sm hover:bg-brand-700"
          >
            Hội thoại mới
          </Link>
        }
      />

      <Warnings items={["API /api/v1 chưa có endpoint liệt kê hội thoại theo người dùng (docs/11 section 2). Danh sách dưới đây được lưu cục bộ trên trình duyệt."]} />

      {entries.length === 0 ? (
        <EmptyState
          icon="🗂️"
          message="Chưa có hội thoại nào được mở trên trình duyệt này. Hãy đặt câu hỏi ở màn hình Chat."
          action={{ label: "Mở màn hình Chat", onClick: () => navigate("/chat") }}
        />
      ) : (
        <Panel title={`Đã lưu ${entries.length} hội thoại`}>
          {isLoading && <LoadingSpinner text="Đang đọc hội thoại từ server..." />}
          <ul className="divide-y divide-slate-200">
            {entries.map((entry, index) => {
              const result = results[index];
              const detail = result?.data;
              const title = detail?.conversation.title || entry.title || "(không có tiêu đề)";
              const messageCount = detail?.messages.length;
              return (
                <li key={entry.conversation_id} className="py-3 flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="font-medium text-slate-900 truncate">{truncate(title, 90)}</div>
                    <div className="text-xs text-slate-500 font-mono truncate">
                      {entry.conversation_id}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      {messageCount != null ? `${messageCount} tin nhắn · ` : ""}
                      cập nhật {formatDateTime(detail?.conversation.updated_at ?? entry.updated_at)}
                      {detail?.conversation.is_archived && " · đã lưu trữ"}
                    </div>
                    {result?.isError && (
                      <p className="text-xs text-rose-600 mt-1">
                        {envelopeMessage(result.error)} (hội thoại có thể đã bị xóa hoặc ngoài quyền
                        truy cập).
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <button
                      onClick={() => navigate(`/chat?conversation=${entry.conversation_id}`)}
                      className="rounded-lg border border-brand-200 text-brand-700 px-3 py-1 text-xs hover:bg-brand-50"
                    >
                      Mở
                    </button>
                    <button
                      onClick={() => handleForget(entry.conversation_id)}
                      className="text-xs text-slate-400 hover:text-rose-600"
                    >
                      Bỏ khỏi danh sách
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </Panel>
      )}
    </div>
  );
}
