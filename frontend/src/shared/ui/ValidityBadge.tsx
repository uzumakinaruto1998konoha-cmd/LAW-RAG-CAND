import React from "react";

/**
 * Validity labels for the statuses defined in docs/06 section 4 / ValidityStatus.
 * Unknown codes are shown verbatim so the server stays the source of truth.
 */
const VALIDITY_VI: Record<string, string> = {
  in_force: "Còn hiệu lực",
  not_yet_effective: "Chưa có hiệu lực",
  partially_effective: "Hiệu lực một phần",
  amended: "Đã được sửa đổi",
  expired: "Hết hiệu lực",
  repealed: "Bị bãi bỏ",
  conflict: "Có xung đột",
  pending: "Chờ hiệu lực",
  unknown: "Chưa xác minh",
};

const VALIDITY_CLASSES: Record<string, string> = {
  in_force: "bg-emerald-100 text-emerald-700",
  not_yet_effective: "bg-brand-50 text-brand-700",
  partially_effective: "bg-amber-100 text-amber-700",
  amended: "bg-amber-100 text-amber-700",
  conflict: "bg-rose-100 text-rose-700",
  expired: "bg-slate-200 text-slate-600",
  repealed: "bg-rose-100 text-rose-700",
  pending: "bg-amber-100 text-amber-700",
  unknown: "bg-slate-100 text-slate-500",
};

export function ValidityBadge({ status }: { status: string }) {
  const cls = VALIDITY_CLASSES[status] || VALIDITY_CLASSES.unknown;
  const label = VALIDITY_VI[status] || status;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}
      title={`validity_status: ${status}`}
    >
      {label}
    </span>
  );
}
