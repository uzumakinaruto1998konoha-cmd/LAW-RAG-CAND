import React, { useState } from "react";
import { useAuth } from "../features/auth/authContext";
import { envelopeMessage } from "../shared/api/client";
import { useDocuments } from "../shared/api/useDocuments";
import {
  JobStatusResponse,
  newIdempotencyKey,
  UploadResponse,
  useJobStatus,
  useUploadDocument,
} from "../shared/api/useIngestion";
import { formatBytes, formatDateTime, isTerminalJobStatus, jobStatusLabel } from "../shared/format";
import {
  EmptyState,
  ErrorState,
  LoadingSpinner,
  PageHeader,
  Panel,
  PermissionDenied,
  Warnings,
  useToast,
} from "../shared/ui";

const ADMIN_PERMISSIONS = [
  "document.upload",
  "document.view",
  "index.manage",
  "collection.manage",
  "audit.view",
];

/** Capabilities still missing from /api/v1 (docs/11 section 2, ADR-010, PHASE 6-8). */
const PENDING_CAPABILITIES = [
  {
    title: "Duyệt và release phiên bản",
    detail:
      "Workflow review/approve đã có ở tầng ingestion nhưng chưa mở endpoint HTTP: chưa thể duyệt, sửa metadata hay release từ UI (docs/16, hạng mục PHASE 5 Admin UI đang Pending).",
  },
  {
    title: "Index manifests (build/rebuild/rollback)",
    detail: "Chưa có endpoint manifests; chỉ có số liệu tổng hợp qua /ready.",
  },
  {
    title: "Người dùng và vai trò",
    detail:
      "Ma trận vai trò RBAC hiện là mặc định của deployment (ADR-010 còn Open); chưa có API quản trị user/role.",
  },
  {
    title: "Audit events",
    detail:
      "Quyền audit.view chỉ mở được chi tiết trace theo mã; chưa có endpoint liệt kê sự kiện audit.",
  },
  {
    title: "Backup/restore",
    detail: "Thuộc PHASE 8 (docs/14); chưa có API vận hành.",
  },
];

export default function AdminPage() {
  const { user, hasPermission } = useAuth();
  const canUpload = hasPermission("document.upload");
  const canViewDocuments = hasPermission("document.view");
  const hasAnyAdminPermission = ADMIN_PERMISSIONS.some((permission) => hasPermission(permission));

  if (!hasAnyAdminPermission) {
    return (
      <PermissionDenied
        requiredPermission={ADMIN_PERMISSIONS.join(" / ")}
        message="Tài khoản của bạn không có quyền quản trị (upload, kho tài liệu, index, audit)."
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <PageHeader
        title="Quản trị"
        description="Nạp tài liệu, theo dõi job ingestion và tổng quan knowledge base. Máy chủ vẫn là nơi quyết định quyền cuối cùng."
      />

      <Panel
        title="Quyền hiệu lực của bạn"
        description="Server trả về trong /me; UI chỉ dùng để ẩn/hiện chức năng."
      >
        <div className="flex flex-wrap gap-1">
          {(user?.permissions ?? []).map((permission) => (
            <code
              key={permission}
              className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700"
            >
              {permission}
            </code>
          ))}
        </div>
      </Panel>

      {canUpload ? (
        <UploadSection />
      ) : (
        <Panel title="Nạp tài liệu">
          <PermissionDenied
            requiredPermission="document.upload"
            message="Bạn không có quyền nạp tài liệu."
          />
        </Panel>
      )}

      {canViewDocuments && <KnowledgeBaseOverview />}

      <Panel
        title="Chưa khả dụng trong /api/v1"
        description="Các chức năng quản trị còn thiếu endpoint; nêu rõ để không hiểu nhầm là đã hoàn tất."
      >
        <ul className="space-y-2 text-sm">
          {PENDING_CAPABILITIES.map((item) => (
            <li key={item.title} className="rounded-lg border border-slate-200 p-3">
              <div className="flex items-center gap-2">
                <span className="font-medium text-slate-800">{item.title}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                  chưa có API
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">{item.detail}</p>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function UploadSection() {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [receipt, setReceipt] = useState<UploadResponse | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const upload = useUploadDocument();
  const toast = useToast();

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setReceipt(null);
    // One key per file selection: a retry of the same file must not re-ingest it.
    setIdempotencyKey(selected ? newIdempotencyKey() : "");
  }

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      toast("Vui lòng chọn tệp để nạp.", "warning");
      return;
    }
    const key = idempotencyKey || newIdempotencyKey();
    try {
      const response = await upload.mutateAsync({
        file,
        idempotencyKey: key,
        source: source.trim() || undefined,
      });
      setReceipt(response);
      setJobId(response.job_id);
      toast(
        response.duplicate_match
          ? "Tệp trùng nội dung đã có; job hiện tại trỏ tới bản gốc."
          : "Đã nhận tệp và tạo job ingestion.",
        response.duplicate_match ? "warning" : "success"
      );
    } catch {
      // Toast is raised by the hook.
    }
  }

  return (
    <Panel
      title="Nạp tài liệu (ingestion v1)"
      description="PDF, DOCX, TXT (UTF-8), JPG/JPEG, PNG; tối đa 50 MiB. Tệp được kiểm tra chữ ký nội dung trước khi lưu blob bất biến."
    >
      <form onSubmit={handleUpload} className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            Tệp
            <input
              type="file"
              accept=".pdf,.docx,.txt,.jpg,.jpeg,.png"
              onChange={handleFileChange}
              className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            Nguồn (tuỳ chọn)
            <input
              value={source}
              onChange={(event) => setSource(event.target.value)}
              placeholder="Ví dụ: do cơ quan ban hành cung cấp"
              className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div className="text-xs text-slate-500">
            Idempotency-Key
            <div className="font-mono text-xs text-slate-700 break-all">
              {idempotencyKey || "(tạo khi chọn tệp)"}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIdempotencyKey(newIdempotencyKey())}
            className="rounded-lg border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100"
          >
            Tạo khóa mới
          </button>
          <button
            type="submit"
            disabled={upload.isPending}
            className="ml-auto rounded-lg bg-brand-600 text-white px-4 py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            {upload.isPending ? "Đang tải lên..." : "Tải lên"}
          </button>
        </div>
      </form>

      {upload.isPending && <LoadingSpinner text="Đang tải tệp lên server..." />}

      {upload.isError && !upload.isPending && (
        <Warnings tone="danger" items={[envelopeMessage(upload.error)]} />
      )}

      {receipt && (
        <div className="rounded-lg border border-slate-200 p-3 space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium text-slate-800">Job {receipt.job_id}</span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              {jobStatusLabel(receipt.status)}
            </span>
            {receipt.duplicate_match && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                trùng nội dung
              </span>
            )}
          </div>
          <dl className="grid gap-2 sm:grid-cols-2 text-xs text-slate-600">
            <div>
              <dt className="text-slate-400">Tệp</dt>
              <dd>
                {receipt.original_filename} · {receipt.media_type} ·{" "}
                {formatBytes(receipt.size_bytes)}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">SHA-256</dt>
              <dd className="font-mono break-all">{receipt.sha256}</dd>
            </div>
            <div>
              <dt className="text-slate-400">document_id / version_id</dt>
              <dd>
                {receipt.document_id ?? "—"} / {receipt.version_id ?? "—"} — chỉ có sau khi phiên bản
                được duyệt và release
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Trace</dt>
              <dd className="font-mono break-all">{receipt.trace_id}</dd>
            </div>
          </dl>
          <Warnings items={receipt.warnings} />
        </div>
      )}

      {jobId && <JobStatusPanel jobId={jobId} />}
    </Panel>
  );
}

function JobStatusPanel({ jobId }: { jobId: string }) {
  const job = useJobStatus(jobId);

  if (job.isLoading) return <LoadingSpinner text="Đang đọc trạng thái job..." />;
  if (job.isError) {
    return (
      <ErrorState
        message={`${envelopeMessage(job.error)} — job chỉ hiển thị cho người tải lên hoặc vai trò audit.view.`}
        onRetry={() => job.refetch()}
      />
    );
  }
  if (!job.data) return null;

  const status: JobStatusResponse = job.data;
  return (
    <div className="rounded-lg border border-slate-200 p-3 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-slate-900">Trạng thái job</h3>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
          {jobStatusLabel(status.status)}
        </span>
        {!isTerminalJobStatus(status.status) && (
          <span className="text-xs text-slate-400">đang tự động làm mới…</span>
        )}
        <button
          onClick={() => job.refetch()}
          className="ml-auto rounded-lg border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100"
        >
          Làm mới
        </button>
      </div>
      <dl className="grid gap-2 sm:grid-cols-2 text-xs text-slate-600">
        <div>
          <dt className="text-slate-400">Lần thử</dt>
          <dd>{status.attempt}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Mã lỗi</dt>
          <dd>{status.error_code ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Người tải lên</dt>
          <dd className="font-mono break-all">{status.uploader_id}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Cập nhật</dt>
          <dd>{formatDateTime(status.updated_at)}</dd>
        </div>
      </dl>
      {status.error_code && (
        <Warnings
          tone="danger"
          items={[
            `Job kết thúc với mã lỗi ${status.error_code}. Job thất bại không tự chạy lại; thao tác retry/review chưa có endpoint (docs/11 section 2).`,
          ]}
        />
      )}
    </div>
  );
}

function KnowledgeBaseOverview() {
  const documents = useDocuments();
  const all = documents.data?.documents ?? [];

  const byValidity = all.reduce<Record<string, number>>((accumulator, item) => {
    accumulator[item.validity_status] = (accumulator[item.validity_status] ?? 0) + 1;
    return accumulator;
  }, {});
  const totalChunks = all.reduce((sum, item) => sum + item.chunk_count, 0);
  const unverified = all.filter((item) => !item.is_verified).length;

  if (documents.isLoading) {
    return (
      <Panel title="Tổng quan knowledge base">
        <LoadingSpinner text="Đang đọc kho tài liệu..." />
      </Panel>
    );
  }

  if (documents.isError) {
    return (
      <Panel title="Tổng quan knowledge base">
        <ErrorState
          message={envelopeMessage(documents.error)}
          onRetry={() => documents.refetch()}
        />
      </Panel>
    );
  }

  if (all.length === 0) {
    return (
      <Panel title="Tổng quan knowledge base">
        <EmptyState
          icon="📚"
          message="Chưa có phiên bản tài liệu nào được release trong phạm vi quyền của bạn."
        />
      </Panel>
    );
  }

  return (
    <Panel
      title="Tổng quan knowledge base"
      description={`${all.length} phiên bản tài liệu bạn được đọc`}
    >
      <dl className="grid gap-3 sm:grid-cols-3 text-sm">
        <div>
          <dt className="text-xs text-slate-500">Tổng chunk đã index</dt>
          <dd className="text-slate-800">{totalChunks}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Chưa duyệt</dt>
          <dd className="text-slate-800">{unverified}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Theo trạng thái hiệu lực</dt>
          <dd className="text-slate-800">
            {Object.entries(byValidity).map(([status, count]) => (
              <span key={status} className="mr-2">
                {status}: {count}
              </span>
            ))}
          </dd>
        </div>
      </dl>
      <Warnings
        tone="info"
        items={[
          "Số liệu chỉ tính các phiên bản bạn được phép đọc; /ready (trang Trạng thái hệ thống) là nguồn cho số chunk toàn hệ thống.",
        ]}
      />
    </Panel>
  );
}
