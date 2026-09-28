import React from "react";

export function LoadingSpinner({ size = "h-6 w-6", text }: { size?: string; text?: string }) {
  return (
    <div className="flex items-center gap-2 text-slate-500 text-sm">
      <div className={`${size} animate-spin rounded-full border-2 border-slate-300 border-t-brand-600`} />
      {text && <span>{text}</span>}
    </div>
  );
}