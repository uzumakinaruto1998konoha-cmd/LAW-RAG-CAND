import React from "react";

interface Props {
  message?: string;
  icon?: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ message = "Không có dữ liệu.", icon = "📭", action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="text-4xl mb-3">{icon}</div>
      <p className="text-slate-600 text-sm">{message}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-3 rounded-lg bg-brand-600 text-white px-4 py-2 text-sm hover:bg-brand-700"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}