import React from "react";
import { Link } from "react-router-dom";
import { envelopeMessage } from "../shared/api/client";
import { useHealth, useReadiness } from "../shared/api/useHealth";
import { formatDateTime } from "../shared/format";
import { ErrorState, LoadingSpinner, PageHeader, Panel, Warnings } from "../shared/ui";

export default function HealthPage() {
  const health = useHealth();
  const readiness = useReadiness();

  const degraded = readiness.data?.status === "degraded";

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <PageHeader
        title="Trạng thái hệ thống"
        description="Endpoint /health và /ready không yêu cầu xác thực và không trả dữ liệu nhạy cảm."
        actions={
          <button
            onClick={() => {
              health.refetch();
              readiness.refetch();
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            Làm mới
          </button>
        }
      />

      <Panel title="Liveness">
        {health.isLoading && <LoadingSpinner text="Đang kiểm tra..." />}
        {health.isError && !health.isLoading && (
          <ErrorState
            message={`${envelopeMessage(health.error)} — API có thể chưa chạy.`}
            onRetry={() => health.refetch()}
          />
        )}
        {health.data && (
          <dl className="grid gap-3 sm:grid-cols-3 text-sm">
            <div>
              <dt className="text-xs text-slate-500">Trạng thái</dt>
              <dd className="text-emerald-600 font-medium">{health.data.status}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Phase</dt>
              <dd className="text-slate-800">{health.data.phase}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Kiến trúc</dt>
              <dd className="text-slate-800 font-mono text-xs">
                {health.data.architecture_version}
              </dd>
            </div>
          </dl>
        )}
      </Panel>

      <Panel title="Readiness">
        {readiness.isLoading && <LoadingSpinner text="Đang kiểm tra subsystem..." />}
        {readiness.isError && !readiness.isLoading && (
          <ErrorState
            message={envelopeMessage(readiness.error)}
            onRetry={() => readiness.refetch()}
          />
        )}
        {readiness.data && (
          <>
            {degraded && (
              <Warnings
                title="Hệ thống đang ở trạng thái suy giảm"
                items={[
                  "Một số subsystem chưa sẵn sàng; kết quả tìm kiếm có thể thiếu hoặc index có thể đang lệch (stale index).",
                ]}
              />
            )}
            <dl className="grid gap-3 sm:grid-cols-3 text-sm">
              <div>
                <dt className="text-xs text-slate-500">Trạng thái</dt>
                <dd
                  className={
                    degraded ? "text-amber-600 font-medium" : "text-emerald-600 font-medium"
                  }
                >
                  {readiness.data.status}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Chunk đã index</dt>
                <dd className="text-slate-800">{readiness.data.indexed_chunk_count}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Phiên bản đã index</dt>
                <dd className="text-slate-800">{readiness.data.indexed_version_count}</dd>
              </div>
            </dl>
            <ul className="divide-y divide-slate-100 text-sm">
              {readiness.data.checks.map((check) => (
                <li key={check.name} className="py-2 flex items-start justify-between gap-3">
                  <div>
                    <div className="text-slate-800">{check.name}</div>
                    {check.detail && <div className="text-xs text-slate-500">{check.detail}</div>}
                  </div>
                  <span
                    className={
                      check.status === "ok"
                        ? "text-xs text-emerald-600"
                        : "text-xs text-amber-600 font-medium"
                    }
                  >
                    {check.status}
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-slate-400">
              Hiển thị lúc {formatDateTime(new Date().toISOString())} · tự động làm mới mỗi 30 giây.
            </p>
          </>
        )}
      </Panel>

      <div className="flex gap-3 text-sm">
        <Link to="/search" className="text-brand-600 hover:underline">
          ← Về tra cứu
        </Link>
        <Link to="/dev/login" className="text-slate-500 hover:underline">
          Đăng nhập lại
        </Link>
      </div>
    </div>
  );
}
