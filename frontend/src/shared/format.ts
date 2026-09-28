/**
 * Presentation helpers for the Phase 5 pages (docs/12).
 *
 * Formatting only: no legal vocabulary, thresholds, or retrieval defaults are
 * hard-coded here. Status codes are rendered as human labels, and any code the
 * UI does not know is shown verbatim so the server remains the source of truth.
 */

const DASH = "—";

export function formatDate(value?: string | null): string {
  if (!value) return DASH;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function formatDateTime(value?: string | null): string {
  if (!value) return DASH;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatScore(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return DASH;
  return value.toFixed(3);
}

export function pageRange(start?: number | null, end?: number | null): string {
  if (start == null && end == null) return DASH;
  if (start != null && end != null && start !== end) return `trang ${start}–${end}`;
  return `trang ${start ?? end}`;
}

export function formatBytes(size?: number | null): string {
  if (size == null || Number.isNaN(size)) return DASH;
  if (size < 1024) return `${size} B`;
  const kilobytes = size / 1024;
  if (kilobytes < 1024) return `${kilobytes.toFixed(1)} KB`;
  return `${(kilobytes / 1024).toFixed(2)} MB`;
}

const JOB_STATUS_LABELS: Record<string, string> = {
  uploaded: "Đã nhận tệp",
  quarantined: "Cách ly",
  queued: "Trong hàng đợi",
  extracting: "Đang trích xuất",
  ocr: "Đang OCR",
  parsing: "Đang phân tích cấu trúc",
  review_required: "Cần người duyệt",
  approved: "Đã duyệt",
  indexing: "Đang lập chỉ mục",
  indexed: "Đã lập chỉ mục",
  failed: "Thất bại",
  superseded: "Đã được thay thế",
  archived: "Đã lưu trữ",
};

export function jobStatusLabel(status?: string | null): string {
  if (!status) return DASH;
  return JOB_STATUS_LABELS[status] ?? status;
}

const CITATION_STATUS_LABELS: Record<string, string> = {
  valid: "Đã kiểm chứng",
  invalid: "Không hợp lệ",
  pending: "Chờ kiểm chứng",
};

/** Citation validation status produced server-side (docs/09). */
export function citationStatusLabel(status?: string | null): string {
  if (!status) return DASH;
  return CITATION_STATUS_LABELS[status] ?? status;
}

const TERMINAL_JOB_STATUSES = new Set([
  "review_required",
  "approved",
  "indexed",
  "failed",
  "superseded",
  "archived",
]);

/** Terminal states stop the UI job poller; the list mirrors the ingestion lifecycle. */
export function isTerminalJobStatus(status?: string | null): boolean {
  return !!status && TERMINAL_JOB_STATUSES.has(status);
}

export function truncate(text: string, max = 160): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  return normalized.length <= max ? normalized : `${normalized.slice(0, max).trimEnd()}…`;
}

export function titleFromQuestion(question: string, max = 60): string {
  return truncate(question, max);
}

export function isVerifiedLabel(isVerified: boolean): string {
  return isVerified ? "Đã duyệt" : "Chưa duyệt";
}
