import type { HealthStatus, ProjectInfo } from "../api";

export type ConnectionState = "idle" | "checking" | "connected" | "error";

interface ConnectionStatusProps {
  state: ConnectionState;
  projectInfo: ProjectInfo | null;
  health: HealthStatus | null;
  error: string;
}

interface StatusVisual {
  dot: string;
  ring: string;
  label: string;
  message: string;
}

function getStatusVisual(state: ConnectionState, error: string): StatusVisual {
  switch (state) {
    case "checking":
      return {
        dot: "bg-blue-400",
        ring: "bg-blue-400/20",
        label: "Checking connection…",
        message: "Contacting the backend, please wait.",
      };
    case "connected":
      return {
        dot: "bg-emerald-400",
        ring: "bg-emerald-400/20",
        label: "Backend connected",
        message: "The FastAPI backend responded successfully.",
      };
    case "error":
      return {
        dot: "bg-rose-400",
        ring: "bg-rose-400/20",
        label: "Connection failed",
        message: error || "Could not reach the backend.",
      };
    default:
      return {
        dot: "bg-slate-500",
        ring: "bg-slate-500/20",
        label: "Not connected",
        message: "Click the button below to check the backend.",
      };
  }
}

export default function ConnectionStatus({
  state,
  projectInfo,
  health,
  error,
}: ConnectionStatusProps) {
  const visual = getStatusVisual(state, error);

  return (
    <div className="space-y-4">
      {/* Status indicator row */}
      <div className="flex items-center gap-3">
        <div className="relative flex h-3 w-3">
          {state === "checking" && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
          )}
          <span
            className={`relative inline-flex h-3 w-3 rounded-full ${visual.dot}`}
          />
        </div>
        <span className="font-medium text-slate-100">{visual.label}</span>
      </div>

      {/* Message */}
      <p className="text-sm text-slate-400">{visual.message}</p>

      {/* Loading spinner */}
      {state === "checking" && (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <svg className="h-4 w-4 animate-spin text-blue-400" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
            />
          </svg>
          Waiting for response…
        </div>
      )}

      {/* Error detail */}
      {state === "error" && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      {/* Connected details */}
      {state === "connected" && projectInfo && health && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Backend Response
          </h3>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-slate-500">Service</dt>
              <dd className="font-mono text-sm text-slate-100">
                {projectInfo.name}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Version</dt>
              <dd className="font-mono text-sm text-slate-100">
                v{projectInfo.version}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Health</dt>
              <dd className="font-mono text-sm text-emerald-300">
                {health.status}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Server time</dt>
              <dd className="font-mono text-xs text-slate-300">
                {new Date(health.timestamp).toLocaleString()}
              </dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  );
}
