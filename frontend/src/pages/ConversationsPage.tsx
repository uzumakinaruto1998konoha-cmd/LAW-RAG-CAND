import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { envelopeMessage } from "../shared/api/client";
import { useConversations } from "../shared/api/useChat";
import { formatDateTime, truncate } from "../shared/format";
import {
  EmptyState,
  LoadingSpinner,
  PageHeader,
  Panel,
} from "../shared/ui";

/**
 * Conversations owned by the authenticated caller, queried from GET /conversations.
 *
 * Each conversation row links to `/chat?conversation={id}` where messages and
 * citations are loaded with full ACL and citation verification.
 */
export default function ConversationsPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useConversations();

  const conversations = data?.conversations ?? [];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <PageHeader
        title="Hội thoại"
        description="Danh sách các phiên hội thoại của bạn; nội dung được lưu trữ và kiểm soát quyền tập trung trên hệ thống."
        actions={
          <Link
            to="/chat"
            className="rounded-lg bg-brand-600 text-white px-3 py-2 text-sm hover:bg-brand-700"
          >
            Hội thoại mới
          </Link>
        }
      />

      {isLoading && <LoadingSpinner text="Đang tải danh sách hội thoại..." />}

      {isError && (
        <Panel title="Lỗi tải hội thoại">
          <p className="text-sm text-rose-600">{envelopeMessage(error)}</p>
        </Panel>
      )}

      {!isLoading && !isError && conversations.length === 0 && (
        <EmptyState
          icon="🗂️"
          message="Bạn chưa có phiên hội thoại nào trên hệ thống. Hãy bắt đầu đặt câu hỏi pháp luật tại màn hình Chat."
          action={{ label: "Mở màn hình Chat", onClick: () => navigate("/chat") }}
        />
      )}

      {!isLoading && !isError && conversations.length > 0 && (
        <Panel title={`Danh sách ${conversations.length} hội thoại`}>
          <ul className="divide-y divide-slate-200">
            {conversations.map((item) => {
              const title = item.title || "(không có tiêu đề)";
              return (
                <li key={item.conversation_id} className="py-3 flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="font-medium text-slate-900 truncate">{truncate(title, 90)}</div>
                    <div className="text-xs text-slate-500 font-mono truncate">
                      {item.conversation_id}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      cập nhật {formatDateTime(item.updated_at)}
                      {item.is_archived && " · đã lưu trữ"}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <button
                      onClick={() => navigate(`/chat?conversation=${item.conversation_id}`)}
                      className="rounded-lg border border-brand-200 text-brand-700 px-3 py-1 text-xs hover:bg-brand-50 font-medium"
                    >
                      Mở hội thoại
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

