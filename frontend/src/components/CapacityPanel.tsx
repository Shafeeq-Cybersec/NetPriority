/**
 * CapacityPanel — Phase 2 Link Capacity Estimator display.
 *
 * Shows:
 *   - Utilisation gauge bar with congestion colour coding
 *   - Snapshot metrics: observed throughput, jitter, active flows
 *   - Per-category bandwidth breakdown bars
 *   - Limitation disclaimer (always visible — values are metadata-derived)
 *   - Link speed input so the user can change the denominator
 */

import { useState } from "react";
import type {
  CapacityEstimate,
  CongestionState,
} from "../api";

interface CapacityPanelProps {
  estimate: CapacityEstimate | null;
  loading: boolean;
  error: string;
  linkSpeedMbps: number;
  onLinkSpeedChange: (mbps: number) => void;
  onRefresh: () => void;
}

// ── congestion colours ──────────────────────────────────────────────────────
const CONGESTION_STYLES: Record<
  CongestionState,
  { bar: string; badge: string; label: string }
> = {
  clear:     { bar: "bg-emerald-400", badge: "bg-emerald-500/20 text-emerald-300", label: "Clear" },
  moderate:  { bar: "bg-amber-400",   badge: "bg-amber-500/20  text-amber-300",   label: "Moderate" },
  congested: { bar: "bg-rose-400",    badge: "bg-rose-500/20   text-rose-300",    label: "Congested" },
};

const CATEGORY_COLORS: Record<string, string> = {
  Gaming:    "bg-violet-400",
  Video:     "bg-blue-400",
  Signaling: "bg-amber-400",
  Bulk:      "bg-rose-400",
  Unknown:   "bg-slate-500",
};

function fmt(mbps: number): string {
  if (mbps >= 1) return `${mbps.toFixed(2)} Mbps`;
  return `${(mbps * 1000).toFixed(1)} Kbps`;
}

export default function CapacityPanel({
  estimate,
  loading,
  error,
  linkSpeedMbps,
  onLinkSpeedChange,
  onRefresh,
}: CapacityPanelProps) {
  const [editSpeed, setEditSpeed] = useState(String(linkSpeedMbps));

  const snap = estimate?.snapshot ?? null;
  const congStyle = snap
    ? (CONGESTION_STYLES[snap.congestion_state] ?? CONGESTION_STYLES.clear)
    : CONGESTION_STYLES.clear;

  const handleSpeedSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(editSpeed);
    if (!isNaN(val) && val > 0) {
      onLinkSpeedChange(val);
    }
  };

  return (
    <div className="mb-6 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl">
      {/* Header */}
      <div className="flex flex-col gap-3 border-b border-white/10 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">
            Link Capacity Estimator
          </h2>
          <p className="text-xs text-slate-500">
            Phase 2 · Derived from submitted flow metadata · No live packet capture.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Link speed input */}
          <form onSubmit={handleSpeedSubmit} className="flex items-center gap-1.5">
            <label className="text-xs text-slate-500 whitespace-nowrap">
              Link speed
            </label>
            <input
              type="number"
              value={editSpeed}
              onChange={(e) => setEditSpeed(e.target.value)}
              min="0.1"
              step="1"
              className="w-20 rounded-lg border border-white/10 bg-slate-800/60 px-2 py-1 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
            />
            <span className="text-xs text-slate-500">Mbps</span>
            <button
              type="submit"
              className="rounded-lg border border-white/10 px-2 py-1 text-xs text-slate-400 transition hover:border-white/30 hover:text-slate-200"
            >
              Apply
            </button>
          </form>
          {/* Refresh */}
          <button
            onClick={onRefresh}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-400 transition hover:border-white/30 hover:text-slate-200 disabled:opacity-50"
          >
            <svg
              className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
              viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            >
              <path d="M23 4v6h-6M1 20v-6h6" />
              <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-5 mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-xs text-rose-300">
          {error}
        </div>
      )}

      {/* Content */}
      {snap ? (
        <div className="p-5 space-y-5">

          {/* ── Utilisation gauge ── */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Link Utilisation
                </span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${congStyle.badge}`}>
                  {congStyle.label}
                </span>
              </div>
              <span className="text-sm font-bold text-slate-100">
                {snap.utilisation_pct.toFixed(1)} %
              </span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-white/5">
              <div
                className={`h-full rounded-full transition-all duration-700 ${congStyle.bar}`}
                style={{ width: `${snap.utilisation_pct}%` }}
              />
            </div>
            <div className="mt-1 flex justify-between text-xs text-slate-600">
              <span>0</span>
              <span>{snap.link_speed_mbps} Mbps</span>
            </div>
          </div>

          {/* ── Key metrics grid ── */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric
              label="Observed"
              value={fmt(snap.observed_mbps)}
              sub="throughput"
            />
            <Metric
              label="Active flows"
              value={String(snap.active_flows)}
              sub={`${snap.measurable_flows} measurable`}
            />
            <Metric
              label="Mean jitter"
              value={snap.mean_jitter_ms != null ? `${snap.mean_jitter_ms.toFixed(1)} ms` : "—"}
              sub="inter-arrival"
            />
            <Metric
              label="Max jitter"
              value={snap.max_jitter_ms != null ? `${snap.max_jitter_ms.toFixed(1)} ms` : "—"}
              sub="inter-arrival"
            />
          </div>

          {/* ── Per-category breakdown ── */}
          {(estimate?.by_category.length ?? 0) > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Bandwidth by Category
              </p>
              <div className="space-y-2">
                {estimate!.by_category.map((cat) => (
                  <div key={cat.category}>
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="text-slate-400">{cat.category}</span>
                      <span className="text-slate-300">
                        {fmt(cat.observed_mbps)}
                        <span className="ml-2 text-slate-600">
                          {cat.share_pct.toFixed(1)} %
                        </span>
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          CATEGORY_COLORS[cat.category] ?? "bg-slate-500"
                        }`}
                        style={{ width: `${cat.share_pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Limitation disclaimer ── */}
          <div className="rounded-xl border border-white/5 bg-slate-900/40 px-4 py-2.5">
            <p className="text-xs text-slate-500">
              <span className="font-semibold text-slate-400">Note: </span>
              {snap.limitation}
            </p>
          </div>

          {/* Timestamp */}
          <p className="text-right text-xs text-slate-600">
            Estimated {new Date(snap.estimated_at).toLocaleTimeString()}
          </p>
        </div>
      ) : !loading && !error ? (
        <div className="px-5 py-10 text-center text-sm text-slate-500">
          Submit flows using the form above, then refresh to see the capacity estimate.
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center gap-2 px-5 py-10 text-sm text-slate-500">
          <svg className="h-4 w-4 animate-spin text-indigo-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          Computing estimate…
        </div>
      ) : null}
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-xl border border-white/5 bg-slate-900/40 px-3 py-2.5">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-0.5 text-lg font-bold text-slate-100">{value}</p>
      <p className="text-xs text-slate-600">{sub}</p>
    </div>
  );
}
