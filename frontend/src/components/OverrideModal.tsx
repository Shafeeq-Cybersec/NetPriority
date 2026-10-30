/**
 * OverrideModal — manually correct a misclassification.
 *
 * UX improvement #7:
 *   When the flow has ALREADY been manually overridden before, a clear
 *   warning is shown inside the modal:
 *   "This flow has already been manually corrected. You are replacing
 *    the previous override."
 *   This prevents accidental double-overrides without blocking the action.
 */

import { useState } from "react";
import type { FlowResponse, TrafficCategory } from "../api";

interface OverrideModalProps {
  flow: FlowResponse;
  onConfirm: (category: TrafficCategory, reason: string) => void;
  onCancel: () => void;
  loading: boolean;
}

const CATEGORIES: TrafficCategory[] = ["Gaming", "Video", "Signaling", "Bulk"];

const CATEGORY_COLORS: Record<TrafficCategory, string> = {
  Gaming:    "border-violet-500 bg-violet-500/10 text-violet-300",
  Video:     "border-blue-500  bg-blue-500/10  text-blue-300",
  Signaling: "border-amber-500 bg-amber-500/10 text-amber-300",
  Bulk:      "border-rose-500  bg-rose-500/10  text-rose-300",
  Unknown:   "border-slate-500 bg-slate-500/10 text-slate-400",
};

export default function OverrideModal({
  flow,
  onConfirm,
  onCancel,
  loading,
}: OverrideModalProps) {
  const [category, setCategory] = useState<TrafficCategory>(
    flow.effective_category === "Unknown" ? "Gaming" : flow.effective_category,
  );
  const [reason, setReason] = useState("");

  const alreadyOverridden = flow.is_manually_overridden; // #7

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-slate-900 p-6 shadow-2xl">

        {/* Title */}
        <h3 className="mb-1 text-lg font-semibold text-slate-100">
          Override Classification
        </h3>

        {/* Flow identity */}
        <p className="mb-1 text-xs text-slate-500">
          Flow:{" "}
          <span className="font-mono text-slate-400">
            {flow.src_ip}:{flow.src_port ?? "?"} → {flow.dst_ip}:{flow.dst_port ?? "?"}
          </span>
        </p>
        <p className="mb-4 text-xs text-slate-500">
          Auto classification:{" "}
          <span className="font-semibold text-slate-300">
            {flow.auto_classification.category}
          </span>{" "}
          (confidence {flow.auto_classification.confidence_score}).
          The original result is always preserved for comparison.
        </p>

        {/* Re-override warning (improvement #7) */}
        {alreadyOverridden && (
          <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2.5">
            <svg
              className="mt-0.5 h-4 w-4 shrink-0 text-amber-400"
              viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            >
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
              <path d="M12 9v4M12 17h.01" />
            </svg>
            <div>
              <p className="text-xs font-semibold text-amber-300">
                This flow has already been manually corrected.
              </p>
              <p className="mt-0.5 text-xs text-amber-400/80">
                Current override:{" "}
                <span className="font-medium text-amber-300">
                  {flow.manual_category}
                </span>
                {flow.manual_override_reason && (
                  <> — {flow.manual_override_reason}</>
                )}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Continuing will replace the previous override.
              </p>
            </div>
          </div>
        )}

        {/* Category selector */}
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Corrected Category
        </p>
        <div className="mb-4 grid grid-cols-2 gap-2">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setCategory(cat)}
              className={`rounded-xl border px-4 py-2.5 text-sm font-semibold transition ${
                category === cat
                  ? CATEGORY_COLORS[cat]
                  : "border-white/10 text-slate-400 hover:border-white/20 hover:text-slate-200"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Reason */}
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
          Reason (optional)
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
          rows={3}
          placeholder="e.g. Confirmed this is a cloud backup, not gaming traffic."
          className="mb-5 w-full resize-none rounded-xl border border-white/10 bg-slate-800/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-indigo-500 focus:outline-none"
        />

        {/* Actions */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="flex-1 rounded-xl border border-white/10 py-2.5 text-sm text-slate-400 transition hover:border-white/30 hover:text-slate-200 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(category, reason)}
            disabled={loading}
            className="flex-1 rounded-xl bg-gradient-to-r from-indigo-500 to-cyan-500 py-2.5 text-sm font-semibold text-white shadow-lg transition hover:opacity-90 disabled:opacity-50"
          >
            {loading
              ? "Applying…"
              : alreadyOverridden
              ? "Replace Override"
              : "Apply Override"}
          </button>
        </div>
      </div>
    </div>
  );
}
