/**
 * FlowList — table of all submitted flows.
 *
 * UX improvements over previous version:
 *   - Live text filter: searches src_ip, dst_ip, port, category as you type.
 *   - "Source" column replaces "Override" column.
 *     "auto"      grey badge  — classified by the rule engine.
 *     "corrected" green badge — administrator manually overrode the result.
 *   - Refresh button shows explicit feedback via onRefresh callback.
 */

import { useMemo, useState } from "react";
import type { FlowResponse, TrafficCategory } from "../api";

interface FlowListProps {
  flows: FlowResponse[];
  selectedId: string | null;
  onSelect: (flow: FlowResponse) => void;
  onRefresh: () => void;
  refreshing: boolean;
}

const CATEGORY_BADGE: Record<TrafficCategory, string> = {
  Gaming:    "bg-violet-500/20 text-violet-300",
  Video:     "bg-blue-500/20 text-blue-300",
  Signaling: "bg-amber-500/20 text-amber-300",
  Bulk:      "bg-rose-500/20 text-rose-300",
  Unknown:   "bg-slate-500/20 text-slate-400",
};

export default function FlowList({
  flows,
  selectedId,
  onSelect,
  onRefresh,
  refreshing,
}: FlowListProps) {
  const [query, setQuery] = useState("");

  // --- live filter (improvement #1) ---
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [...flows].reverse();
    return [...flows]
      .reverse()
      .filter((f) => {
        const port = (p: number | null) => (p != null ? String(p) : "");
        return (
          f.src_ip.toLowerCase().includes(q) ||
          f.dst_ip.toLowerCase().includes(q) ||
          port(f.src_port).includes(q) ||
          port(f.dst_port).includes(q) ||
          f.protocol.toLowerCase().includes(q) ||
          f.effective_category.toLowerCase().includes(q) ||
          f.auto_classification.category.toLowerCase().includes(q)
        );
      });
  }, [flows, query]);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl">
      {/* Header */}
      <div className="flex flex-col gap-3 border-b border-white/10 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">
            Submitted Flows
          </h2>
          <p className="text-xs text-slate-500">
            {flows.length} flow{flows.length !== 1 ? "s" : ""} in registry
            {query && filtered.length !== flows.length && (
              <> · {filtered.length} matching</>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Live search (improvement #1) */}
          <div className="relative">
            <svg
              className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500"
              viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by IP, port, category…"
              className="rounded-lg border border-white/10 bg-slate-800/60 py-1.5 pl-8 pr-3 text-xs text-slate-200 placeholder-slate-600 focus:border-indigo-500 focus:outline-none w-48"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Refresh */}
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-400 transition hover:border-white/30 hover:text-slate-200 disabled:opacity-50"
          >
            <svg
              className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
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

      {/* Table */}
      {flows.length === 0 ? (
        <div className="px-5 py-10 text-center text-sm text-slate-500">
          No flows yet. Submit one using the form above.
        </div>
      ) : filtered.length === 0 ? (
        <div className="px-5 py-8 text-center text-sm text-slate-500">
          No flows match <span className="font-mono text-slate-400">"{query}"</span>.{" "}
          <button onClick={() => setQuery("")} className="text-indigo-400 underline underline-offset-2 hover:text-indigo-300">
            Clear filter
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-left">
                <Th>Source</Th>
                <Th>Destination</Th>
                <Th>Proto</Th>
                <Th>Category</Th>
                <Th>Confidence</Th>
                {/* Improvement #2 — "Source" replaces "Override" */}
                <Th>Source</Th>
                <Th>Submitted</Th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((flow) => {
                const isSelected = flow.flow_id === selectedId;
                return (
                  <tr
                    key={flow.flow_id}
                    onClick={() => onSelect(flow)}
                    className={`cursor-pointer border-b border-white/5 transition-colors last:border-0 ${
                      isSelected ? "bg-indigo-500/10" : "hover:bg-white/5"
                    }`}
                  >
                    <Td>
                      <span className="font-mono text-xs">
                        {flow.src_ip}
                        {flow.src_port != null && (
                          <span className="text-slate-500">:{flow.src_port}</span>
                        )}
                      </span>
                    </Td>
                    <Td>
                      <span className="font-mono text-xs">
                        {flow.dst_ip}
                        {flow.dst_port != null && (
                          <span className="text-slate-500">:{flow.dst_port}</span>
                        )}
                      </span>
                    </Td>
                    <Td>
                      <span className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-xs text-slate-400">
                        {flow.protocol}
                      </span>
                    </Td>
                    <Td>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                          CATEGORY_BADGE[flow.effective_category] ??
                          CATEGORY_BADGE.Unknown
                        }`}
                      >
                        {flow.effective_category}
                      </span>
                    </Td>
                    <Td>
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/10">
                          <div
                            className="h-full rounded-full bg-indigo-400"
                            style={{
                              width: `${flow.auto_classification.confidence_score}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-slate-400">
                          {flow.auto_classification.confidence_score}
                        </span>
                      </div>
                    </Td>
                    {/* Source badge (improvement #2) */}
                    <Td>
                      {flow.is_manually_overridden ? (
                        <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-xs font-semibold text-emerald-300">
                          corrected
                        </span>
                      ) : (
                        <span className="rounded-full bg-slate-500/15 px-2.5 py-0.5 text-xs font-semibold text-slate-500">
                          auto
                        </span>
                      )}
                    </Td>
                    <Td>
                      <span className="text-xs text-slate-500">
                        {new Date(flow.created_at).toLocaleTimeString()}
                      </span>
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
      {children}
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 text-slate-300">{children}</td>;
}
