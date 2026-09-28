import React, { useCallback, useRef, useState } from "react";
import { Toast, ToastContext, ToastVariant } from "./toastContext";

/** Renders transient feedback pushed by any screen through `useToast()`. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(1);

  const push = useCallback((message: string, variant: ToastVariant = "info") => {
    const id = seq.current++;
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const variantClasses: Record<ToastVariant, string> = {
    info: "bg-brand-600 text-white",
    success: "bg-emerald-600 text-white",
    error: "bg-rose-600 text-white",
    warning: "bg-amber-500 text-slate-900",
  };

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`rounded-lg shadow-lg px-4 py-3 text-sm max-w-sm ${variantClasses[toast.variant]}`}
          >
            <div className="flex items-start justify-between gap-3">
              <span>{toast.message}</span>
              <button
                onClick={() => remove(toast.id)}
                className="opacity-70 hover:opacity-100"
                aria-label="Đóng thông báo"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
