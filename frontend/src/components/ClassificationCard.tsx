/**
 * ClassificationCard — displays the result of a single flow classification.
 * Shows category, confidence bar, reason text and matched rule names.
 */

import type { FlowResponse, TrafficCategory } from "../api";

interface ClassificationCardProps {
  flow: FlowResponse;
}

const CATEGORY_STYLES: Record<
  TrafficCategory,
  { bg: string; border: string; badge: string; text: string; bar: string }
> = {
  Gaming: {
    bg: "bg-violet-500/10",
    border: "border-violet-500/30",
    badge: "bg-violet-500/20 text-violet-300",
    text: "text-violet-300",
    bar: "bg-violet-400",
  },
  Video: {
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    badge: "bg-blue-500/20 text-blue-300",
    text: "text-blue-300",
    bar: "bg-blue-400",
  },
  Signaling: {
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    badge: "bg-amber-500/20 text-amber-300",
    text: "text-amber-300",
    bar: "bg-amber-400",
  },
  Bulk: {
    bg: "bg-rose-500/10",
    border: "border-rose-500/30",
    badge: "bg-rose-500/20 text-rose-300",
    text: "text-rose-300",
    bar: "bg-rose-400",
  },
  Unknown: {
    bg: "bg-slate-500/10",
    border: "border-slate-500/30",
    badge: "bg-slate-500/20 text-slate-400",
    text: "text-slate-400",
    bar: "bg-slate-500",
  },
};

export default function ClassificationCard({ flow }: ClassificationCardProps) {
  const result = flow.auto_classification;
  const effective = flow.effective_category;
  const style = CATEGORY_STYLES[effective] ?? CATEGORY_STYLES.Unknown;

  return (
    <div
      className={`rounded-2xl border ${style.border} ${style.bg} p-5 backdrop-blur-xl`}
    >
      {/* Header row */}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-500">
            Classification Result
          </p>
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-sm font-bold ${style.badge}`}
            >
              {effective}
            </span>
            {flow.is_manually_overridden && (
              <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-medium text-emerald-300">
                manually overridden
              </span>
            )}
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">Confidence</p>
          <p className={`text-2xl font-bold ${style.text}`}>
            {result.confidence_score}
          </p>
          <p className="text-xs text-slate-600">/ 100</p>
        </div>
      </div>

      {/* Confidence bar */}
      <div className="mb-4 h-2 w-full overflow-hidden rounded-full bg-white/5">
        <div
          className={`h-full rounded-full transition-all duration-500 ${style.bar}`}
          style={{ width: `${result.confidence_score}%` }}
        />
      </div>

      {/* QoS marking recommendation derived from the effective category */}
      <div
        className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-white/10 bg-slate-950/30 px-3 py-2"
        title={flow.qos.treatment}
      >
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          QoS
        </span>
        <span className="font-mono text-xs text-slate-300">
          DSCP {flow.qos.dscp} · {flow.qos.dscp_class}
        </span>
        <span className="text-xs text-slate-500">
          Queue {flow.qos.queue} · {flow.qos.priority} priority
        </span>
      </div>

      {/* If overridden, show both original and override */}
      {flow.is_manually_overridden && (
        <div className="mb-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs text-slate-400">
          <span className="font-medium text-emerald-400">Override:</span>{" "}
          {flow.manual_category}
          {flow.manual_override_reason && (
            <> — {flow.manual_override_reason}</>
          )}
          <br />
          <span className="text-slate-500">
            Original auto classification:{" "}
            <span className="font-medium text-slate-400">
              {result.category}
            </span>{" "}
            (confidence {result.confidence_score})
          </span>
        </div>
      )}

      {/* Reason */}
      <div className="mb-3">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Reason
        </p>
        <p className="text-xs leading-relaxed text-slate-300">
          {result.reason}
        </p>
      </div>

      {/* Matched rules */}
      {result.matched_rules.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Matched Rules
          </p>
          <div className="flex flex-wrap gap-1.5">
            {result.matched_rules.map((rule) => (
              <span
                key={rule}
                className="rounded-md bg-white/5 px-2 py-0.5 font-mono text-xs text-slate-400"
              >
                {rule}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Flow ID */}
      <p className="mt-4 font-mono text-xs text-slate-600">
        {flow.flow_id}
      </p>
    </div>
  );
}
