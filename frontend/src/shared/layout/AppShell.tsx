import React, { useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../features/auth/authContext";
import { useToast } from "../ui";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  /** Permission that reveals the entry; hidden client-side, enforced on the server. */
  permission?: string;
}

const NAV: NavItem[] = [
  { to: "/search", label: "Tìm kiếm", icon: "🔍" },
  { to: "/chat", label: "Chat", icon: "💬" },
  { to: "/conversations", label: "Hội thoại", icon: "🗂️" },
  { to: "/documents", label: "Kho tài liệu", icon: "📚" },
  { to: "/admin", label: "Quản trị", icon: "⚙️", permission: "document.upload" },
];

function isActive(pathname: string, target: string): boolean {
  return pathname === target || pathname.startsWith(`${target}/`);
}

export function AppShell({ children }: { children?: React.ReactNode }) {
  const { user, logout, hasPermission } = useAuth();
  const toast = useToast();
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  function handleLogout() {
    logout();
    toast("Đã đăng xuất.", "info");
  }

  const visibleNav = NAV.filter((item) => !item.permission || hasPermission(item.permission));
  const currentLabel =
    NAV.filter((item) => isActive(location.pathname, item.to)).sort(
      (a, b) => b.to.length - a.to.length
    )[0]?.label || "LAW-RAG";

  return (
    <div className="flex h-screen bg-slate-50">
      <aside
        className={`flex flex-col border-r border-slate-200 bg-white transition-all duration-200 ${
          collapsed ? "w-16" : "w-64"
        }`}
      >
        <div className="flex items-center gap-2 px-4 py-4 border-b border-slate-200">
          <div className="h-9 w-9 rounded-lg bg-brand-600 text-white flex items-center justify-center font-bold">
            ⚖
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="font-semibold text-slate-900 truncate">LAW-RAG</div>
              <div className="text-xs text-slate-500 truncate">Tra cứu pháp luật</div>
            </div>
          )}
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {visibleNav.map((item) => {
            const active = isActive(location.pathname, item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                title={item.label}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-brand-50 text-brand-700 font-medium"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <span className="text-base" aria-hidden="true">
                  {item.icon}
                </span>
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>
        <div className="p-2 border-t border-slate-200">
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
            aria-expanded={!collapsed}
          >
            <span aria-hidden="true">{collapsed ? "▶" : "◀"}</span>
            {!collapsed && <span>Rút gọn</span>}
          </button>
          <div className="mt-1 rounded-lg px-3 py-2 text-xs text-slate-500 truncate">
            {user?.display_name}
          </div>
          <button
            onClick={handleLogout}
            className="w-full mt-1 rounded-lg px-3 py-2 text-sm text-rose-600 hover:bg-rose-50"
          >
            Đăng xuất
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur px-6 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-slate-900">{currentLabel}</h1>
          <Link to="/health" className="text-xs text-slate-500 hover:text-brand-600">
            Trạng thái hệ thống
          </Link>
        </header>
        <div className="p-6">{children ?? <Outlet />}</div>
      </main>
    </div>
  );
}
