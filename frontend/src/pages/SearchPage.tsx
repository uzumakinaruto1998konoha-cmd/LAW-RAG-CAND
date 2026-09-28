import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { envelopeMessage } from "../shared/api/client";
import { useSearch, SearchResult } from "../shared/api/useSearch";
import { formatScore, pageRange } from "../shared/format";
import {
  EmptyState,
  ErrorState,
  LoadingSpinner,
  PageHeader,
  Panel,
  ValidityBadge,
  Warnings,
  useToast,
} from "../shared/ui";

type QueryType = "hybrid" | "lexical" | "semantic";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [asOfDate, setAsOfDate] = useState("");
  const [queryType, setQueryType] = useState<QueryType>("hybrid");
  const [documentType, setDocumentType] = useState("");
  const [issuingBody, setIssuingBody] = useState("");
  const [collectionId, setCollectionId] = useState("");
  const search = useSearch();
  const toast = useToast();
  const navigate = useNavigate();

  function buildFilters(): Record<string, string> | undefined {
    const filters: Record<string, string> = {};
    if (documentType.trim()) filters.document_type = documentType.trim();
    if (issuingBody.trim()) filters.issuing_body = issuingBody.trim();
    if (collectionId.trim()) filters.collection_id = collectionId.trim();
    return Object.keys(filters).length > 0 ? filters : undefined;
  }

  async function runSearch() {
    const trimmed = query.trim();
    if (!trimmed) {
      toast("Vui lòng nhập câu hỏi.", "warning");
      return;
    }
    try {
      await search.mutateAsync({
        query: trimmed,
        top_k: topK,
        as_of_date: asOfDate || undefined,
        query_type: queryType,
        filters: buildFilters(),
      });
    } catch {
      // Toast is raised by the hook; the inline error state below repeats it.
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    void runSearch();
  }

  const data = search.data;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <PageHeader
        title="Tra cứu pháp luật"
        description="Tìm kiếm kết hợp (BM25 + vector) trên knowledge base đã được phân quyền theo ACL phía server."
        actions={
          <Link
            to="/chat"
            className="rounded-lg border border-brand-200 text-brand-700 px-3 py-2 text-sm hover:bg-brand-50"
          >
            Chuyển sang hỏi đáp có dẫn chiếu →
          </Link>
        }
      />

      <form onSubmit={handleSubmit} className="space-y-4">
        <Panel>
          <label htmlFor="search-query" className="block text-sm font-medium text-slate-700">
            Câu hỏi hoặc từ khóa
          </label>
          <textarea
            id="search-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={3}
            placeholder="Ví dụ: điều kiện chuyển nhượng quyền sử dụng đất (nhập câu hỏi hoặc từ khóa)"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
          />
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              Ngày áp dụng
              <input
                type="date"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              Top K
              <input
                type="number"
                min={1}
                max={50}
                value={topK}
                onChange={(e) => setTopK(Math.max(1, Math.min(50, Number(e.target.value) || 10)))}
                className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              Kiểu truy vấn
              <select
                value={queryType}
                onChange={(e) => setQueryType(e.target.value as QueryType)}
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="hybrid">Hybrid (BM25 + vector)</option>
                <option value="lexical">Lexical (BM25)</option>
                <option value="semantic">Semantic (vector)</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={search.isPending}
              className="ml-auto rounded-lg bg-brand-600 text-white px-5 py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {search.isPending ? "Đang tìm..." : "Tìm kiếm"}
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
                onChange={(e) => setDocumentType(e.target.value)}
                placeholder="Nhập giá trị loại văn bản"
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              issuing_body
              <input
                value={issuingBody}
                onChange={(e) => setIssuingBody(e.target.value)}
                placeholder="Cơ quan ban hành"
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              collection_id
              <input
                value={collectionId}
                onChange={(e) => setCollectionId(e.target.value)}
                placeholder="Bộ sưu tập được cấp quyền"
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Giá trị lọc lấy từ metadata do ingestion tạo; UI không giới hạn cứng danh mục để tránh
            hai nguồn sự thật.
          </p>
        </details>
      </form>

      {search.isPending && <LoadingSpinner text="Đang truy vấn retrieval engine..." />}

      {search.isError && !search.isPending && (
        <ErrorState message={envelopeMessage(search.error)} onRetry={runSearch} />
      )}

      {data && !search.isPending && !search.isError && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
            <span>
              Tìm thấy <strong className="text-slate-900">{data.result_count}</strong> kết quả
              {data.latency_ms != null && <span className="text-slate-400"> · {data.latency_ms}ms</span>}
              {data.as_of_date && <span className="text-slate-400"> · ngày áp dụng {data.as_of_date}</span>}
            </span>
            <Link to={`/traces/${data.trace_id}`} className="text-xs text-brand-600 hover:underline">
              Xem trace: {data.trace_id}
            </Link>
          </div>

          <Warnings items={data.warnings} />

          {data.results.length === 0 ? (
            <EmptyState
              message="Không có đoạn nào khớp trong phạm vi tài liệu bạn được phép đọc. Điều này không đồng nghĩa với việc vấn đề không được quy định trong pháp luật."
              icon="🔍"
            />
          ) : (
            data.results.map((result) => (
              <ResultCard
                key={result.chunk_id}
                result={result}
                onAsk={() => navigate("/chat", { state: { prefill: data.query } })}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

function ResultCard({ result, onAsk }: { result: SearchResult; onAsk: () => void }) {
  return (
    <article className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs text-slate-400 font-mono">{result.document_number}</div>
          <h3 className="font-medium text-slate-900">{result.document_title}</h3>
          <div className="text-xs text-slate-500">{result.issuing_body}</div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <ValidityBadge status={result.validity_status} />
          <span className="text-xs text-slate-400">score {formatScore(result.score)}</span>
        </div>
      </div>
      <div className="text-xs text-slate-500">
        <span className="font-medium">{result.structural_path}</span>
        {result.heading && <span> · {result.heading}</span>}
        <span> · {pageRange(result.page_start, result.page_end)}</span>
      </div>
      <p className="text-sm text-slate-700 whitespace-pre-wrap">{result.snippet}</p>
      <div className="flex flex-wrap items-center gap-3 pt-1">
        {result.is_verified ? (
          <span className="text-xs text-emerald-600">✓ Đã duyệt</span>
        ) : (
          <span className="text-xs text-amber-600">Chưa duyệt</span>
        )}
        <Link
          to={`/documents/${result.document_id}`}
          className="text-xs text-slate-600 hover:underline"
        >
          Chi tiết tài liệu →
        </Link>
        <button onClick={onAsk} className="ml-auto text-xs text-brand-600 hover:underline">
          Chat về câu hỏi này →
        </button>
      </div>
    </article>
  );
}
