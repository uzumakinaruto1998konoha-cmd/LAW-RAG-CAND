import React from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { envelopeMessage } from "../shared/api/client";
import { useDocument } from "../shared/api/useDocuments";
import { formatDate, isVerifiedLabel, pageRange } from "../shared/format";
import {
  EmptyState,
  ErrorState,
  LoadingSpinner,
  PageHeader,
  Panel,
  ValidityBadge,
} from "../shared/ui";

export default function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const document = useDocument(documentId ?? null);
  const navigate = useNavigate();

  if (document.isLoading) {
    return (
      <div className="max-w-4xl mx-auto">
        <LoadingSpinner text="Đang tải tài liệu..." />
      </div>
    );
  }

  if (document.isError) {
    return (
      <div className="max-w-4xl mx-auto space-y-4">
        <Link to="/documents" className="text-sm text-brand-600 hover:underline">
          ← Kho tài liệu
        </Link>
        <ErrorState
          message={`${envelopeMessage(document.error)} — tài liệu có thể không tồn tại hoặc nằm ngoài quyền đọc của bạn.`}
          onRetry={() => document.refetch()}
        />
      </div>
    );
  }

  if (!document.data) {
    return (
      <div className="max-w-4xl mx-auto">
        <EmptyState icon="📄" message="Không có dữ liệu tài liệu để hiển thị." />
      </div>
    );
  }

  const summary = document.data.document;
  const chunks = document.data.chunks;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Link to="/documents" className="text-sm text-brand-600 hover:underline">
        ← Kho tài liệu
      </Link>

      <PageHeader
        title={summary.title}
        description={`${summary.document_number} · ${summary.issuing_body} · ${summary.document_type}`}
        actions={
          <button
            onClick={() =>
              navigate("/chat", {
                state: {
                  prefill: `Tóm tắt nội dung chính của văn bản ${summary.document_number} và nêu các mốc hiệu lực.`,
                },
              })
            }
            className="rounded-lg bg-brand-600 text-white px-3 py-2 text-sm hover:bg-brand-700"
          >
            Hỏi về văn bản này
          </button>
        }
      />

      <Panel title="Thông tin phiên bản">
        <dl className="grid gap-3 sm:grid-cols-2 text-sm">
          <Field label="Trạng thái hiệu lực">
            <ValidityBadge status={summary.validity_status} />
          </Field>
          <Field label="Trạng thái duyệt">
            <span className={summary.is_verified ? "text-emerald-600" : "text-amber-600"}>
              {isVerifiedLabel(summary.is_verified)}
            </span>
          </Field>
          <Field label="Ngày ban hành">{formatDate(summary.issue_date)}</Field>
          <Field label="Ngày hiệu lực">{formatDate(summary.effective_date)}</Field>
          <Field label="Ngày hết hiệu lực">{formatDate(summary.expiry_date)}</Field>
          <Field label="Số chunk đã index">{summary.chunk_count}</Field>
          <Field label="Bộ sưu tập (ACL)">
            {summary.collection_ids.length > 0 ? (
              <span className="flex flex-wrap gap-1">
                {summary.collection_ids.map((id) => (
                  <code
                    key={id}
                    className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700"
                  >
                    {id}
                  </code>
                ))}
              </span>
            ) : (
              "—"
            )}
          </Field>
          <Field label="Định danh">
            <span className="block font-mono text-xs text-slate-600 break-all">
              document: {summary.document_id}
              <br />
              version: {summary.version_id}
            </span>
          </Field>
        </dl>
      </Panel>

      <Panel
        title={`Cấu trúc và nội dung (${chunks.length} chunk)`}
        description="Chunk giữ ranh giới pháp lý; số trang tương ứng với bản PDF gốc."
      >
        {chunks.length === 0 ? (
          <EmptyState icon="🧩" message="Phiên bản này chưa có chunk nào được index." />
        ) : (
          <ol className="space-y-3">
            {chunks.map((chunk) => (
              <li key={chunk.chunk_id} className="rounded-lg border border-slate-200 p-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span className="font-mono">#{chunk.chunk_index}</span>
                  {chunk.node_kind && (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5">{chunk.node_kind}</span>
                  )}
                  <span className="font-medium text-slate-700">{chunk.structural_path}</span>
                  {chunk.heading && <span>· {chunk.heading}</span>}
                  <span>· {pageRange(chunk.page_start, chunk.page_end)}</span>
                  {chunk.token_count != null && <span>· {chunk.token_count} token</span>}
                </div>
                <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap font-sans text-sm text-slate-700">
                  {chunk.content}
                </pre>
              </li>
            ))}
          </ol>
        )}
      </Panel>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-slate-800">{children}</dd>
    </div>
  );
}
