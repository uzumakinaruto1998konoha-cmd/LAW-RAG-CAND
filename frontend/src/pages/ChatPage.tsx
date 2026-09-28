import React, { useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { useAuth } from "../features/auth/authContext";
import { envelopeMessage } from "../shared/api/client";
import { ChatResponse, CitationModel, useChat, useConversation } from "../shared/api/useChat";
import { rememberConversation } from "../shared/conversations";
import {
  citationStatusLabel,
  formatDateTime,
  formatScore,
  pageRange,
  titleFromQuestion,
} from "../shared/format";
import {
  EmptyState,
  ErrorState,
  LoadingSpinner,
  PageHeader,
  Panel,
  PermissionDenied,
  ValidityBadge,
  Warnings,
  useToast,
} from "../shared/ui";

type QueryType = "hybrid" | "lexical" | "semantic";

interface Turn {
  question: string;
  response: ChatResponse;
}

const INSUFFICIENT_EVIDENCE_NOTES = [
  "Kho tài liệu trong phạm vi bạn được phép truy cập không có đoạn nào đủ căn cứ cho câu hỏi này. Hệ thống không bổ sung kiến thức ngoài căn cứ đã truy xuất.",
  "Thông báo này chỉ phản ánh dữ liệu hiện có và ngày áp dụng đang chọn, không khẳng định vấn đề không được pháp luật quy định.",
];

export default function ChatPage() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const prefill = (location.state as { prefill?: string } | null)?.prefill ?? "";

  const urlConversationId = params.get("conversation");
  const [loadedUrlConversationId, setLoadedUrlConversationId] = useState<string | null>(
    urlConversationId
  );
  const [conversationId, setConversationId] = useState<string | null>(urlConversationId);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState(prefill);
  const [asOfDate, setAsOfDate] = useState("");
  const [topK, setTopK] = useState(5);
  const [queryType, setQueryType] = useState<QueryType>("hybrid");
  const [documentType, setDocumentType] = useState("");
  const [issuingBody, setIssuingBody] = useState("");
  const [collectionId, setCollectionId] = useState("");

  const chat = useChat();
  const history = useConversation(loadedUrlConversationId);
  const toast = useToast();
  const { hasPermission } = useAuth();

  // Opening another conversation from the list resets the local transcript.
  if (urlConversationId !== loadedUrlConversationId) {
    setLoadedUrlConversationId(urlConversationId);
    setConversationId(urlConversationId);
    setTurns([]);
  }

  function buildFilters(): Record<string, string> | undefined {
    const filters: Record<string, string> = {};
    if (documentType.trim()) filters.document_type = documentType.trim();
    if (issuingBody.trim()) filters.issuing_body = issuingBody.trim();
    if (collectionId.trim()) filters.collection_id = collectionId.trim();
    return Object.keys(filters).length > 0 ? filters : undefined;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      toast("Vui lòng nhập câu hỏi.", "warning");
      return;
    }
    try {
      const response = await chat.mutateAsync({
        question: trimmed,
        conversation_id: conversationId ?? undefined,
        as_of_date: asOfDate || undefined,
        top_k: topK,
        query_type: queryType,
        filters: buildFilters(),
      });
      setConversationId(response.conversation_id);
      setTurns((previous) => [...previous, { question: trimmed, response }]);
      setQuestion("");
      rememberConversation({
        conversation_id: response.conversation_id,
        title: titleFromQuestion(trimmed),
        updated_at: new Date().toISOString(),
      });
    } catch {
      // Toast is raised by the hook.
    }
  }

  function startNewConversation() {
    setTurns([]);
    setConversationId(null);
    if (urlConversationId) {
      setLoadedUrlConversationId(null);
      setParams({}, { replace: true });
    }
  }

  if (!hasPermission("chat.query")) {
    return (
      <PermissionDenied
        requiredPermission="chat.query"
        message="Tài khoản của bạn không có quyền hỏi đáp (chat.query)."
      />
    );
  }

  const historyMessages = history.data?.messages ?? [];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <PageHeader
        title="Hỏi đáp có dẫn chiếu"
        description="Câu trả lời chỉ dựa trên căn cứ truy xuất được; citation do server sinh và kiểm chứng."
        actions={
          <button
            onClick={startNewConversation}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            Hội thoại mới
          </button>
        }
      />

      {conversationId && (
        <div className="text-xs text-slate-500">
          Hội thoại hiện tại: <span className="font-mono">{conversationId}</span> ·{" "}
          <Link to="/conversations" className="text-brand-600 hover:underline">
            danh sách hội thoại
          </Link>
        </div>
      )}

      {historyMessages.length > 0 && (
        <Panel title="Lịch sử hội thoại (từ server)" description="Chỉ nội dung tin nhắn được trả về; căn cứ của lượt cũ tra theo trace.">
          <ul className="space-y-3">
            {historyMessages.map((message) => (
              <li key={message.message_id} className="text-sm">
                <div className="text-xs text-slate-400 mb-1">
                  {message.role === "user" ? "Người hỏi" : "Hệ thống"} ·{" "}
                  {formatDateTime(message.created_at)}
                  {message.trace_id && (
                    <>
                      {" · "}
                      <Link
                        to={`/traces/${message.trace_id}`}
                        className="text-brand-600 hover:underline"
                      >
                        trace
                      </Link>
                    </>
                  )}
                </div>
                <div
                  className={
                    message.role === "user"
                      ? "rounded-lg bg-slate-100 px-3 py-2 text-slate-800 whitespace-pre-wrap"
                      : "rounded-lg border border-slate-200 px-3 py-2 text-slate-800 whitespace-pre-wrap"
                  }
                >
                  {message.content}
                </div>
                {message.insufficient_evidence && (
                  <p className="text-xs text-amber-700 mt-1">
                    Lượt trả lời này được đánh dấu không đủ căn cứ.
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {turns.map((turn, index) => (
        <div key={`${turn.response.message_id}-${index}`} className="space-y-3">
          <div className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-800 whitespace-pre-wrap">
            {turn.question}
          </div>
          <AnswerPanel response={turn.response} />
        </div>
      ))}

      {chat.isPending && <LoadingSpinner text="Đang truy xuất căn cứ và tổng hợp câu trả lời..." />}

      {chat.isError && !chat.isPending && (
        <ErrorState message={envelopeMessage(chat.error)} />
      )}

      {!chat.isPending && turns.length === 0 && historyMessages.length === 0 && (
        <EmptyState
          icon="💬"
          message="Nhập câu hỏi pháp lý để nhận câu trả lời có dẫn chiếu tới văn bản, điều khoản và trang nguồn."
        />
      )}

      <form onSubmit={handleSubmit} className="space-y-3">
        <Panel>
          <label htmlFor="chat-question" className="block text-sm font-medium text-slate-700">
            Câu hỏi
          </label>
          <textarea
            id="chat-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={3}
            placeholder="Ví dụ: Thời hạn giải quyết thủ tục đăng ký đất đai lần đầu là bao lâu?"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
          />
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              Ngày áp dụng
              <input
                type="date"
                value={asOfDate}
                onChange={(event) => setAsOfDate(event.target.value)}
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              Số căn cứ (top_k)
              <input
                type="number"
                min={1}
                max={20}
                value={topK}
                onChange={(event) =>
                  setTopK(Math.max(1, Math.min(20, Number(event.target.value) || 5)))
                }
                className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              Kiểu truy vấn
              <select
                value={queryType}
                onChange={(event) => setQueryType(event.target.value as QueryType)}
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="hybrid">Hybrid</option>
                <option value="lexical">Lexical</option>
                <option value="semantic">Semantic</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={chat.isPending}
              className="ml-auto rounded-lg bg-brand-600 text-white px-5 py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {chat.isPending ? "Đang xử lý..." : "Gửi câu hỏi"}
            </button>
          </div>
        </Panel>
        <details className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
          <summary className="cursor-pointer text-sm text-slate-600">
            Bộ lọc theo metadata (khớp chính xác phía server)
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              document_type
              <input
                value={documentType}
                onChange={(event) => setDocumentType(event.target.value)}
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              issuing_body
              <input
                value={issuingBody}
                onChange={(event) => setIssuingBody(event.target.value)}
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              collection_id
              <input
                value={collectionId}
                onChange={(event) => setCollectionId(event.target.value)}
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
          </div>
        </details>
        <p className="text-xs text-slate-400">
          Hệ thống không trả lời bằng kiến thức tự sinh: khi không có căn cứ phù hợp, câu trả lời
          được đánh dấu “không đủ căn cứ” (docs/04).
        </p>
      </form>
    </div>
  );
}

function AnswerPanel({ response }: { response: ChatResponse }) {
  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>
          message <span className="font-mono">{response.message_id}</span>
          {response.as_of_date && <> · ngày áp dụng {response.as_of_date}</>}
        </span>
        <Link to={`/traces/${response.trace_id}`} className="text-brand-600 hover:underline">
          Xem trace
        </Link>
      </div>

      {response.insufficient_evidence && (
        <Warnings title="Không đủ căn cứ" items={INSUFFICIENT_EVIDENCE_NOTES} />
      )}

      <div className="text-sm text-slate-800 whitespace-pre-wrap">{response.answer}</div>

      <Warnings items={response.warnings} />

      {response.citations.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-900">
            Căn cứ ({response.citations.length})
          </h3>
          {response.citations.map((citation, index) => (
            <CitationCard key={citation.citation_id} citation={citation} index={index + 1} />
          ))}
        </section>
      )}

      {response.evidence.length > 0 && (
        <details className="text-xs text-slate-600">
          <summary className="cursor-pointer">
            Đoạn bằng chứng retrieval dùng để trả lời ({response.evidence.length})
          </summary>
          <ul className="mt-2 space-y-2">
            {response.evidence.map((item) => (
              <li key={item.evidence_id} className="rounded-lg border border-slate-200 p-2">
                <div className="flex flex-wrap items-center gap-2 text-slate-500">
                  <span className="font-mono">{item.document_number ?? item.version_id}</span>
                  <ValidityBadge status={item.validity_status} />
                  <span>score {formatScore(item.score)}</span>
                  <span>{pageRange(item.page_start, item.page_end)}</span>
                  <span>{item.is_verified ? "Đã duyệt" : "Chưa duyệt"}</span>
                </div>
                <p className="mt-1 text-slate-700 whitespace-pre-wrap">{item.excerpt}</p>
              </li>
            ))}
          </ul>
        </details>
      )}

      <Link to="/documents" className="text-xs text-slate-500 hover:text-brand-600">
        Mở kho tài liệu để kiểm chứng toàn văn →
      </Link>
    </Panel>
  );
}

function CitationCard({ citation, index }: { citation: CitationModel; index: number }) {
  return (
    <article className="rounded-lg border border-slate-200 p-3 space-y-1">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs text-slate-400 font-mono">
            [{index}] {citation.document_number ?? citation.version_id}
          </div>
          <h4 className="text-sm font-medium text-slate-900">{citation.document_title}</h4>
          <div className="text-xs text-slate-500">
            {citation.issuing_body && <span>{citation.issuing_body} · </span>}
            {citation.structural_path} · {pageRange(citation.page_start, citation.page_end)}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <ValidityBadge status={citation.validity_status} />
          <span className="text-xs text-slate-400">{citationStatusLabel(citation.status)}</span>
        </div>
      </div>
      <p className="text-sm text-slate-700 whitespace-pre-wrap">{citation.excerpt}</p>
      {citation.viewer_url ? (
        <a
          href={citation.viewer_url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-brand-600 hover:underline"
        >
          Mở trang nguồn (viewer) →
        </a>
      ) : (
        <p className="text-xs text-slate-400">
          Chưa có liên kết viewer cho phiên bản này; xác định vị trí theo cấu trúc và số trang ở trên.
        </p>
      )}
    </article>
  );
}
