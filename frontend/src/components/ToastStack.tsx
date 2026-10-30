/**
 * ToastStack — renders the live toast stack in the bottom-right corner.
 * Toasts auto-dismiss after 3 s (controlled by useToast).
 * Each toast can also be manually dismissed by clicking ×.
 */

import type { Toast } from "../hooks/useToast";

interface ToastStackProps {
  toasts: Toast[];
  onDismiss: (id: number) => void;
}

const KIND_STYLES = {
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  error:   "border-rose-500/30    bg-rose-500/10    text-rose-200",
  info:    "border-indigo-500/30  bg-indigo-500/10  text-indigo-200",
};

const KIND_ICON = {
  success: (
    <svg className="h-4 w-4 shrink-0 text-emerald-400" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  ),
  error: (
    <svg className="h-4 w-4 shrink-0 text-rose-400" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v4M12 16h.01" />
    </svg>
  ),
  info: (
    <svg className="h-4 w-4 shrink-0 text-indigo-400" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  ),
};

export default function ToastStack({ toasts, onDismiss }: ToastStackProps) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-center gap-2.5 rounded-xl border px-4 py-2.5 shadow-2xl backdrop-blur-xl
            transition-all duration-300 ${KIND_STYLES[t.kind]}`}
        >
          {KIND_ICON[t.kind]}
          <span className="text-sm font-medium">{t.message}</span>
          <button
            onClick={() => onDismiss(t.id)}
            className="ml-1 opacity-50 transition hover:opacity-100"
            aria-label="Dismiss"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
