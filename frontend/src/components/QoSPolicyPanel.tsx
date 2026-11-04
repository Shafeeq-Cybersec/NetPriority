/**
 * QoSPolicyPanel — shows the category → DSCP / queue marking policy.
 *
 * The classifier decides WHAT a flow is; this table shows how that category
 * is recommended to be marked. Values are policy recommendations only —
 * no packet marking is enforced yet. The currently displayed flow's
 * category is highlighted so the recommendation can be read at a glance.
 */

import type { QoSProfile, TrafficCategory } from "../api";

interface QoSPolicyPanelProps {
  policies: QoSProfile[];
  activeCategory: TrafficCategory | null;
}

const CATEGORY_BADGE: Record<TrafficCategory, string> = {
  Gaming: "bg-violet-500/20 text-violet-300",
  Video: "bg-blue-500/20 text-blue-300",
  Signaling: "bg-amber-500/20 text-amber-300",
  Bulk: "bg-rose-500/20 text-rose-300",
  Unknown: "bg-slate-500/20 text-slate-400",
};

export default function QoSPolicyPanel({
  policies,
  activeCategory,
}: QoSPolicyPanelProps) {
  if (policies.length === 0) return null;

  return (
    <div className="mb-6 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl">
      <div className="border-b border-white/10 px-5 py-4">
        <h2 className="text-lg font-semibold text-slate-100">
          QoS Marking Policy
        </h2>
        <p className="text-xs text-slate-500">
          Category → DSCP / queue recommendations, highest priority first.
          Recommendations only — no packet marking is enforced yet.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/5 text-left">
              <Th>Category</Th>
              <Th>DSCP</Th>
              <Th>Priority</Th>
              <Th>Queue</Th>
              <Th>Treatment</Th>
            </tr>
          </thead>
          <tbody>
            {policies.map((policy) => {
              const isActive = policy.category === activeCategory;
              return (
                <tr
                  key={policy.category}
                  className={`border-b border-white/5 last:border-0 ${
                    isActive ? "bg-indigo-500/10" : ""
                  }`}
                >
                  <Td>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        CATEGORY_BADGE[policy.category] ??
                        CATEGORY_BADGE.Unknown
                      }`}
                    >
                      {policy.category}
                    </span>
                    {isActive && (
                      <span className="ml-2 text-xs text-indigo-300">
                        current
                      </span>
                    )}
                  </Td>
                  <Td>
                    <span className="font-mono text-xs text-slate-300">
                      {policy.dscp}{" "}
                      <span className="text-slate-500">
                        ({policy.dscp_class})
                      </span>
                    </span>
                  </Td>
                  <Td>
                    <span className="text-xs text-slate-400">
                      {policy.priority}
                    </span>
                  </Td>
                  <Td>
                    <span className="font-mono text-xs text-slate-400">
                      {policy.queue}
                    </span>
                  </Td>
                  <Td>
                    <span className="text-xs text-slate-500">
                      {policy.treatment}
                    </span>
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
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
  return <td className="px-4 py-3 align-top text-slate-300">{children}</td>;
}
