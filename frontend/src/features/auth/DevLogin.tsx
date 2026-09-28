import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "./authContext";
import { useToast } from "../../shared/ui";

/**
 * Token entry for local development.
 *
 * Tokens are never hard-coded here (docs/10 and AGENTS.md section 5): the server
 * holds only a SHA-256 digest, and each token is provisioned by the deployment
 * (or by a test harness) for a user with a role from the RBAC matrix.
 */
export function DevLogin() {
  const [token, setToken] = useState("");
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || "/";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token.trim()) {
      toast("Vui lòng nhập bearer token.", "warning");
      return;
    }
    try {
      await login(token.trim());
      navigate(from, { replace: true });
    } catch {
      // toast already shown
    }
  }

  if (user) {
    navigate(from, { replace: true });
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow-lg p-6">
        <h1 className="text-xl font-semibold text-slate-900 mb-1">Đăng nhập</h1>
        <p className="text-sm text-slate-500 mb-6">
          Nhập bearer token để truy cập API <code className="font-mono">/api/v1</code>. Server chỉ
          giữ SHA-256 digest của token, không lưu token gốc.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="bearer-token"
              className="block text-sm font-medium text-slate-700 mb-1"
            >
              Authorization Bearer token
            </label>
            <input
              id="bearer-token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="token-..."
              autoComplete="off"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              autoFocus
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-lg bg-brand-600 text-white py-2 text-sm font-medium hover:bg-brand-700 transition"
          >
            Đăng nhập
          </button>
        </form>
        <details className="mt-6 text-xs text-slate-500">
          <summary className="cursor-pointer">Token lấy ở đâu?</summary>
          <ul className="mt-2 space-y-1 list-disc list-inside">
            <li>
              Token do deployment cấp cho từng tài khoản theo ma trận vai trò RBAC (ADR-009/ADR-010);
              chưa có màn hình quản trị người dùng trong <code className="font-mono">/api/v1</code>.
            </li>
            <li>
              Khi chạy API cục bộ, đăng ký user/token qua <code className="font-mono">ApiContainer</code>{" "}
              (<code className="font-mono">register_user</code>, <code className="font-mono">register_token</code>,
              <code className="font-mono">assign_role</code>) — xem <code className="font-mono">tests/test_api.py</code>.
            </li>
            <li>Không nhúng token thật vào mã nguồn hay cấu hình frontend.</li>
          </ul>
        </details>
      </div>
    </div>
  );
}
