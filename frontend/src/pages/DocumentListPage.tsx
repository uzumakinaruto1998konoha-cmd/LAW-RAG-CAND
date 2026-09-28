import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { envelopeMessage } from "../shared/api/client";
import { useDocuments } from "../shared/api/useDocuments";
import { formatDate, isVerifiedLabel } from "../shared/format";
import {
  EmptyState,
  ErrorState,
  LoadingSpinner,
  PageHeader,
  Panel,
  ValidityBadge,
  Warnings,
} from "../shared/ui";

export default function DocumentListPage() {
  const documents = useDocuments();
  const [text, setText] = useState("");
  const [validity, setValidity] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);

  const all = useMemo(() => documents.data?.documents ?? [], [documents.data]);

  // Filter options are derived from the server payload: the UI keeps no
  // hard-coded validity or document-type vocabulary of its own.
  const validityOptions = useMemo(
    () => Array.from(new Set(all.map((item) => item.validity_status))).sort(),
    [all]
  );
  const typeOptions = useMemo(
    () => Array.from(new Set(all.map((item) => item.document_type))).sort(),
    [all]
  );

  const filtered = useMemo(() => {
    const needle = text.trim().toLowerCase();
    return all.filter((item) => {
      if (validity && item.validity_status !== validity) return false;
      if (documentType && item.document_type !== documentType) return false;
      if (verifiedOnly && !item.is_verified) return false;
      if (!needle) return true;
      return [item.document_number, item.title, item.issuing_body]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [all, text, validity, documentType, verifiedOnly]);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <PageHeader
        title="Kho tài liệu"
        description="Các phiên bản tài liệu đã được release và bạn được phép đọc (ACL kiểm tra phía server)."
      />

      {documents.isLoading && <LoadingSpinner text="Đang tải danh sách tài liệu..." />}

      {documents.isError && !documents.isLoading && (
        <ErrorState
          message={envelopeMessage(documents.error)}
          onRetry={() => documents.refetch()}
        />
      )}

      {documents.data && (
        <>
          <Warnings
            tone="info"
            items={[
              "Endpoint /documents chưa phân trang (docs/11 section 2): toàn bộ tài liệu bạn được đọc được trả trong một lần gọi.",
            ]}
          />

          <Panel title="Bộ lọc">
            <div className="grid gap-3 sm:grid-cols-4">
              <label className="flex flex-col gap-1 text-xs text-slate-600 sm:col-span-2">
                Tìm theo số hiệu, tiêu đề, cơ quan
                <input
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-600">
                Trạng thái hiệu lực
                <select
                  value={validity}
                  onChange={(event) => setValidity(event.target.value)}
                  className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
                >
                  <option value="">Tất cả</option>
                  {validityOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-600">
                Loại văn bản
                <select
                  value={documentType}
                  onChange={(event) => setDocumentType(event.target.value)}
                  className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
                >
                  <option value="">Tất cả</option>
                  {typeOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={verifiedOnly}
                onChange={(event) => setVerifiedOnly(event.target.checked)}
              />
              Chỉ hiện tài liệu đã duyệt
            </label>
          </Panel>

          {filtered.length === 0 ? (
            <EmptyState
              icon="📚"
              message={
                all.length === 0
                  ? "Chưa có tài liệu nào được release trong phạm vi quyền của bạn."
                  : "Không có tài liệu nào khớp bộ lọc hiện tại."
              }
            />
          ) : (
            <Panel
              title={`${filtered.length}/${all.length} tài liệu`}
              description={`Tổng số bản ghi server trả về: ${documents.data.count}`}
            >
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                      <th className="py-2 pr-3">Số hiệu</th>
                      <th className="py-2 pr-3">Tiêu đề</th>
                      <th className="py-2 pr-3">Loại</th>
                      <th className="py-2 pr-3">Ban hành</th>
                      <th className="py-2 pr-3">Hiệu lực</th>
                      <th className="py-2 pr-3">Duyệt</th>
                      <th className="py-2 pr-3">Chunks</th>
                      <th className="py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filtered.map((item) => (
                      <tr key={item.version_id} className="align-top">
                        <td className="py-2 pr-3 font-mono text-xs">{item.document_number}</td>
                        <td className="py-2 pr-3">
                          <div className="text-slate-900">{item.title}</div>
                          <div className="text-xs text-slate-500">
                            {item.issuing_body} · bộ sưu tập:{" "}
                            {item.collection_ids.length > 0 ? item.collection_ids.join(", ") : "—"}
                          </div>
                        </td>
                        <td className="py-2 pr-3 text-xs text-slate-600">{item.document_type}</td>
                        <td className="py-2 pr-3 text-xs text-slate-600">
                          {formatDate(item.issue_date)}
                        </td>
                        <td className="py-2 pr-3">
                          <ValidityBadge status={item.validity_status} />
                          <div className="text-xs text-slate-500 mt-1">
                            hiệu lực từ {formatDate(item.effective_date)}
                            {item.expiry_date && <> · đến {formatDate(item.expiry_date)}</>}
                          </div>
                        </td>
                        <td className="py-2 pr-3 text-xs">
                          <span
                            className={item.is_verified ? "text-emerald-600" : "text-amber-600"}
                          >
                            {isVerifiedLabel(item.is_verified)}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-xs text-slate-600">{item.chunk_count}</td>
                        <td className="py-2 text-right">
                          <Link
                            to={`/documents/${item.document_id}`}
                            className="text-xs text-brand-600 hover:underline"
                          >
                            Chi tiết →
                          </Link>
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
    </div>
  );
}
