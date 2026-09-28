import { createContext, useContext } from "react";

export type ToastVariant = "info" | "success" | "error" | "warning";

export interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
}

/** Toast entry point: call `toast(message, variant)` from any component. */
export type ToastPush = (message: string, variant?: ToastVariant) => void;

export const ToastContext = createContext<ToastPush | null>(null);

export function useToast(): ToastPush {
  const push = useContext(ToastContext);
  if (!push) throw new Error("useToast must be used within ToastProvider");
  return push;
}
