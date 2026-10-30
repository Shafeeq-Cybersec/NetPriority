/**
 * StatusBar — slim single-line bar showing registry size, last action
 * and timestamp. Sits between the flow list and the footer.
 */

interface StatusBarProps {
  flowCount: number;
  lastAction: string;
  lastActionTime: Date | null;
}

export default function StatusBar({
  flowCount,
  lastAction,
  lastActionTime,
}: StatusBarProps) {
  return (
    <div className="mt-4 flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.02] px-4 py-2">
      <div className="flex items-center gap-4 text-xs text-slate-500">
        <span>
          <span className="font-semibold text-slate-300">{flowCount}</span>{" "}
          {flowCount === 1 ? "flow" : "flows"} in registry
        </span>
        {lastAction && (
          <span className="hidden sm:inline">
            Last action:{" "}
            <span className="text-slate-400">{lastAction}</span>
          </span>
        )}
      </div>
      {lastActionTime && (
        <span className="text-xs text-slate-600">
          {lastActionTime.toLocaleTimeString()}
        </span>
      )}
    </div>
  );
}
