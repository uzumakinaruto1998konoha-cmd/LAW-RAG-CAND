import React from "react";

interface PanelProps {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

/** Card container used by every Phase 5 screen for a consistent surface. */
export function Panel({ title, description, actions, children, className = "" }: PanelProps) {
  return (
    <section
      className={`bg-white rounded-xl shadow-sm border border-slate-200 p-4 space-y-3 ${className}`}
    >
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title && <h2 className="font-semibold text-slate-900">{title}</h2>}
            {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
