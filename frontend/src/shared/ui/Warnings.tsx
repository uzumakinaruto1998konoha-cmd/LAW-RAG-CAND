import React from "react";

export type WarningTone = "warning" | "info" | "danger";

const TONE_CLASSES: Record<WarningTone, string> = {
  warning: "bg-amber-50 border-amber-200 text-amber-800",
  info: "bg-brand-50 border-brand-100 text-brand-700",
  danger: "bg-rose-50 border-rose-200 text-rose-700",
};

const TONE_ICONS: Record<WarningTone, string> = {
  warning: "⚠",
  info: "ℹ",
  danger: "⛔",
};

interface WarningsProps {
  items: string[];
  tone?: WarningTone;
  title?: string;
}

/**
 * Server-provided warnings (conflicts, unverified validity, stale index, ...).
 * Renders nothing when the server reported no warning, so empty states stay honest.
 */
export function Warnings({ items, tone = "warning", title }: WarningsProps) {
  if (!items || items.length === 0) return null;
  return (
    <div className={`rounded-lg border px-3 py-2 text-sm ${TONE_CLASSES[tone]}`} role="note">
      {title && <div className="font-medium mb-1">{title}</div>}
      <ul className="space-y-1">
        {items.map((item, index) => (
          <li key={`${index}-${item}`}>
            <span aria-hidden="true">{TONE_ICONS[tone]} </span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
