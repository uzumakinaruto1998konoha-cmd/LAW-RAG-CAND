import React from "react";
import { Link, useParams } from "react-router-dom";
import { envelopeMessage } from "../shared/api/client";
import { useTrace } from "../shared/api/useTrace";
import { formatDateTime, formatScore } from "../shared/format";
import {
  EmptyState,
  ErrorState,
  LoadingSpinner,
  PageHeader,
  Panel,
} from "../shared/ui";

export default function TracePage() {
  const { traceId } = useParams<{ traceId: string }>();
  const trace = useTrace(traceId ?? null);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Link to="/search" className="text-sm text-brand-600 hover:underline">
        ← Tra cứu
      </Link>

      <PageHeader
        title="Retrieval trace"
        description="Bản ghi audit của một truy vấn: tham số, ngày áp dụng, manifest và thứ hạng chunk. Trace không chứa nội dung văn bản."
      />

      {trace.isLoading && <LoadingSpinner text="Đang tải trace..." />}

      {trace.isError && !trace.isLoading && (
        <ErrorState
          message={`${envelopeMessage(trace.error)} — trace chỉ hiển thị cho chủ truy vấn hoặc vai trò audit.view.`}
          onRetry={() => trace.refetch()}
        />
      )}

      {trace.data && (
        <>
          <Panel title="Thông tin truy vấn">
            <dl className="grid gap-3 sm:grid-cols-2 text-sm">
              <Field label="Trace id">
                <span className="font-mono text-xs break-all">{trace.data.trace_id}</span>
              </Field>
              <Field label="Người truy vấn">
                <span className="font-mono text-xs">{trace.data.user_id}</span>
              </Field>
              <Field label="Câu truy vấn">{trace.data.query}</Field>
              <Field label="Kiểu truy vấn">{trace.data.query_type}</Field>
              <Field label="Ngày áp dụng">{trace.data.as_of_date ?? "—"}</Field>
              <Field label="Manifest index">{trace.data.manifest_id ?? "—"}</Field>
              <Field label="Thời điểm">{formatDateTime(trace.data.created_at)}</Field>
              <Field label="Độ trễ">
                {trace.data.latency_ms != null ? `${trace.data.latency_ms} ms` : "—"}
              </Field>
              <Field label="Số kết quả">{trace.data.result_count}</Field>
              <Field label="Bộ lọc">
                {trace.data.filters && Object.keys(trace.data.filters).length > 0 ? (
                  <span className="flex flex-wrap gap-1">
                    {Object.entries(trace.data.filters).map(([key, value]) => (
                      <code
                        key={key}
                        className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700"
                      >
                        {key}={String(value)}
                      </code>
                    ))}
                  </span>
                ) : (
                  "—"
                )}
              </Field>
            </dl>
          </Panel>

          {trace.data.results.length === 0 ? (
            <EmptyState icon="🧾" message="Truy vấn này không trả về kết quả nào." />
          ) : (
            <Panel title={`Kết quả truy xuất (${trace.data.results.length})`}>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                      <th className="py-2 pr-3">Hạng</th>
                      <th className="py-2 pr-3">Chunk</th>
                      <th className="py-2 pr-3">Điểm</th>
                      <th className="py-2 pr-3">Phương thức</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {trace.data.results.map((result) => (
                      <tr key={`${result.rank}-${result.chunk_id}`}>
                        <td className="py-2 pr-3 text-slate-600">{result.rank}</td>
                        <td className="py-2 pr-3 font-mono text-xs">{result.chunk_id}</td>
                        <td className="py-2 pr-3 text-slate-600">{formatScore(result.score)}</td>
                        <td className="py-2 pr-3 text-xs text-slate-600">
                          {result.retrieval_method}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </>
      )}

      {!trace.isLoading && !trace.isError && !trace.data && (
        <EmptyState icon="🧾" message="Không tìm thấy trace." />
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-slate-800 break-words">{children}</dd>
    </div>
  );
}
