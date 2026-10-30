/**
 * BackendStatus — shows a live indicator of whether the FastAPI backend
 * is reachable. Fires a HEAD request to /api/health on mount and after
 * every API error reported by the parent.
 *
 * States:
 *   checking    — initial probe in progress
 *   connected   — most recent probe succeeded
 *   disconnected — most recent probe failed (network error, not HTTP 4xx/5xx)
 *
 * Important: HTTP 422 Validation errors from the classifier are normal
 * API responses, not connectivity failures. Only network-level errors
 * (fetch throws, no response) change the state to "disconnected".
 */

export type BackendState = "checking" | "connected" | "disconnected";

interface BackendStatusProps {
  state: BackendState;
  onRetry: () => void;
}

const STYLES: Record<
  BackendState,
  { dot: string; ping: boolean; label: string; labelColor: string }
> = {
  checking: {
    dot: "bg-blue-400",
    ping: true,
    label: "Checking…",
    labelColor: "text-slate-400",
  },
  connected: {
    dot: "bg-emerald-400",
    ping: false,
    label: "Backend connected",
    labelColor: "text-slate-400",
  },
  disconnected: {
    dot: "bg-rose-400",
    ping: false,
    label: "Backend unreachable",
    labelColor: "text-rose-400",
  },
};

export default function BackendStatus({ state, onRetry }: BackendStatusProps) {
  const s = STYLES[state];
  return (
    <div className="flex items-center gap-2">
      {/* Status dot */}
      <div className="relative flex h-2 w-2">
        {s.ping && (
          <span
            className={`absolute inline-flex h-full w-full animate-ping rounded-full ${s.dot} opacity-75`}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${s.dot}`} />
      </div>

      <span className={`text-xs ${s.labelColor}`}>{s.label}</span>

      {/* Retry button when disconnected */}
      {state === "disconnected" && (
        <button
          onClick={onRetry}
          className="text-xs text-rose-400 underline underline-offset-2 transition hover:text-rose-200"
        >
          retry
        </button>
      )}

      {/* API docs link when connected */}
      {state === "connected" && (
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="rounded-full border border-white/10 px-2 py-0.5 text-xs text-slate-500 transition hover:border-white/30 hover:text-slate-300"
        >
          API docs ↗
        </a>
      )}
    </div>
  );
}
