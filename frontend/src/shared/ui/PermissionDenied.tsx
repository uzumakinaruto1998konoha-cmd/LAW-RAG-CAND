import React from "react";

interface PermissionDeniedProps {
  /** Permission the server would require for this screen (shown for transparency). */
  requiredPermission?: string;
  message?: string;
}

/**
 * Role-gated screens are hidden client-side, but the API stays the final
 * decision point (docs/12 section 5). This state explains why nothing is shown.
 */
export function PermissionDenied({ requiredPermission, message }: PermissionDeniedProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="text-4xl mb-3" aria-hidden="true">
        🔒
      </div>
      <p className="text-slate-700 text-sm font-medium">
        {message ?? "Bạn không có quyền truy cập màn hình này."}
      </p>
      {requiredPermission && (
        <p className="text-xs text-slate-500 mt-1">
          Quyền yêu cầu: <code className="font-mono">{requiredPermission}</code> — liên hệ quản trị
          viên để được cấp qua vai trò.
        </p>
      )}
    </div>
  );
}
