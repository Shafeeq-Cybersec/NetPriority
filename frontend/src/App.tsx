import { useCallback, useEffect, useRef, useState } from "react";
import {
  getHealthStatus,
  listFlows,
  listQoSPolicies,
  overrideClassification,
  submitFlow,
  type FlowResponse,
  type FlowSubmit,
  type QoSProfile,
  type TrafficCategory,
} from "./api";
import BackendStatus, { type BackendState } from "./components/BackendStatus";
import ClassificationCard from "./components/ClassificationCard";
import FlowForm from "./components/FlowForm";
import FlowList from "./components/FlowList";
import OverrideModal from "./components/OverrideModal";
import QoSPolicyPanel from "./components/QoSPolicyPanel";
import StatusBar from "./components/StatusBar";
import ToastStack from "./components/ToastStack";
import { useToast } from "./hooks/useToast";

type LoadStatus = "idle" | "loading" | "error";

export default function App() {
  // ── registry ──────────────────────────────────────────────────────────────
  const [flows, setFlows] = useState<FlowResponse[]>([]);
  const [flowsStatus, setFlowsStatus] = useState<LoadStatus>("idle");

  // ── QoS marking policy ────────────────────────────────────────────────────
  const [qosPolicies, setQosPolicies] = useState<QoSProfile[]>([]);

  // ── latest submit result ──────────────────────────────────────────────────
  const [lastResult, setLastResult] = useState<FlowResponse | null>(null);
  const [submitStatus, setSubmitStatus] = useState<LoadStatus>("idle");
  const [submitError, setSubmitError] = useState("");

  // ── selected flow (list row click) ────────────────────────────────────────
  const [selectedFlow, setSelectedFlow] = useState<FlowResponse | null>(null);

  // ── override modal ────────────────────────────────────────────────────────
  const [showOverride, setShowOverride] = useState(false);
  const [overrideStatus, setOverrideStatus] = useState<LoadStatus>("idle");

  // ── backend connectivity (#5) ─────────────────────────────────────────────
  const [backendState, setBackendState] = useState<BackendState>("checking");
  const probeInFlight = useRef(false);

  // ── status bar (#4) ───────────────────────────────────────────────────────
  const [lastAction, setLastAction] = useState("");
  const [lastActionTime, setLastActionTime] = useState<Date | null>(null);

  const recordAction = (msg: string) => {
    setLastAction(msg);
    setLastActionTime(new Date());
  };

  // ── toasts (#3) ───────────────────────────────────────────────────────────
  const { toasts, push: pushToast, dismiss: dismissToast } = useToast();

  // ── backend probe (#5) ────────────────────────────────────────────────────
  // Only network-level failures (fetch throws, no HTTP response at all)
  // mark the backend as disconnected. HTTP 4xx/5xx are valid API responses.
  const probeBackend = useCallback(async () => {
    if (probeInFlight.current) return;
    probeInFlight.current = true;
    setBackendState("checking");
    try {
      await getHealthStatus();
      setBackendState("connected");
    } catch {
      setBackendState("disconnected");
    } finally {
      probeInFlight.current = false;
    }
  }, []);

  useEffect(() => {
    void probeBackend();
  }, [probeBackend]);

  // ── fetch flows list ──────────────────────────────────────────────────────
  const fetchFlows = useCallback(async (silent = false) => {
    if (!silent) setFlowsStatus("loading");
    try {
      const data = await listFlows();
      setFlows(data);
      setFlowsStatus("idle");
      // A successful list fetch confirms backend is reachable
      if (backendState !== "connected") setBackendState("connected");
      return data;
    } catch (err) {
      setFlowsStatus("error");
      // Distinguish network failure from API error
      if (err instanceof TypeError) {
        // TypeError = network unreachable (fetch threw)
        setBackendState("disconnected");
      }
      return null;
    }
  }, [backendState]);

  useEffect(() => {
    void fetchFlows();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── fetch the QoS policy table once ───────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    listQoSPolicies()
      .then((data) => {
        if (!cancelled) setQosPolicies(data);
      })
      .catch(() => {
        // Policy table is supplementary — the classifier still works without it.
        if (!cancelled) setQosPolicies([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // ── submit flow ───────────────────────────────────────────────────────────
  const handleSubmit = async (flow: FlowSubmit) => {
    setSubmitStatus("loading");
    setSubmitError("");
    setLastResult(null);
    try {
      const result = await submitFlow(flow);
      setLastResult(result);
      setSelectedFlow(result);
      setSubmitStatus("idle");
      // Confirm backend is alive
      if (backendState !== "connected") setBackendState("connected");
      // Success toast (#3)
      pushToast(`Classified as ${result.effective_category}`, "success");
      // Status bar (#4)
      recordAction(
        `Classified ${result.src_ip}:${result.src_port ?? "?"} → ${result.dst_ip} as ${result.effective_category}`,
      );
      void fetchFlows(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Submission failed.";
      setSubmitError(msg);
      setSubmitStatus("error");
      // Only flag as disconnected on network error, not validation errors (#5)
      if (err instanceof TypeError) setBackendState("disconnected");
    }
  };

  // ── select flow from list ─────────────────────────────────────────────────
  const handleSelect = (flow: FlowResponse) => {
    setSelectedFlow(flow);
    setLastResult(null);
  };

  // ── open override modal ───────────────────────────────────────────────────
  const handleOverrideOpen = () => {
    if (!selectedFlow) return;
    setShowOverride(true);
  };

  // ── apply override ────────────────────────────────────────────────────────
  const handleOverrideConfirm = async (
    category: TrafficCategory,
    reason: string,
  ) => {
    if (!selectedFlow) return;
    setOverrideStatus("loading");
    try {
      const updated = await overrideClassification(selectedFlow.flow_id, {
        category,
        reason: reason.trim() || undefined,
      });
      setSelectedFlow(updated);
      setFlows((prev) =>
        prev.map((f) => (f.flow_id === updated.flow_id ? updated : f)),
      );
      if (lastResult?.flow_id === updated.flow_id) setLastResult(updated);
      setOverrideStatus("idle");
      setShowOverride(false);
      // Success toast (#3)
      pushToast(`Override applied — ${category}`, "success");
      // Status bar (#4)
      recordAction(`Override: ${updated.src_ip} classified as ${category}`);
    } catch (err) {
      setOverrideStatus("idle");
      pushToast(
        err instanceof Error ? err.message : "Override failed.",
        "error",
      );
      if (err instanceof TypeError) setBackendState("disconnected");
    }
  };

  // ── refresh handler ───────────────────────────────────────────────────────
  const handleRefresh = async () => {
    const data = await fetchFlows();
    if (data) {
      // Success feedback in status bar (#4)
      recordAction(`Refreshed — ${data.length} flow${data.length !== 1 ? "s" : ""}`);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  const displayFlow = lastResult ?? selectedFlow;

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-slate-950 font-sans text-slate-100">
      {/* Background orbs */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="animate-float-slow absolute -left-48 top-0 h-96 w-96 rounded-full bg-indigo-600/15 blur-3xl" />
        <div className="animate-float-slow absolute -right-48 top-1/3 h-96 w-96 rounded-full bg-cyan-500/15 blur-3xl [animation-delay:4s]" />
        <div className="animate-float-slow absolute bottom-0 left-1/3 h-80 w-80 rounded-full bg-violet-600/10 blur-3xl [animation-delay:8s]" />
      </div>

      {/* ── Header ── */}
      <header className="relative border-b border-white/5 bg-slate-950/80 px-6 py-4 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 shadow-lg shadow-indigo-500/30">
              <svg
                className="h-5 w-5 text-white"
                viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              >
                <path d="M6 18V10M6 10L9.5 13.5M6 10L2.5 13.5M18 14V6M18 6L14.5 9.5M18 6L21.5 9.5" />
                <circle cx="12" cy="12" r="2.5" />
              </svg>
            </div>
            <div>
              <span className="bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-lg font-bold text-transparent">
                NetPriority
              </span>
              <span className="ml-2 rounded-full bg-indigo-500/20 px-2 py-0.5 text-xs font-medium text-indigo-300">
                Phase 1
              </span>
            </div>
          </div>

          {/* Backend status indicator (#5) */}
          <BackendStatus state={backendState} onRetry={probeBackend} />
        </div>
      </header>

      {/* ── Main ── */}
      <main className="relative mx-auto max-w-6xl px-4 py-8">
        {/* Page title */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-100">
            Traffic Classifier
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Submit flow metadata · get a classification · browse results ·
            correct misclassifications.
            <br />
            <span className="text-slate-600">
              No payloads inspected. Rule-based engine · 43 tests pass.
            </span>
          </p>
        </div>

        {/* ── Top two-column section ── */}
        <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Form (#6 — Custom mode inside) */}
          <FlowForm
            onSubmit={(f) => void handleSubmit(f)}
            loading={submitStatus === "loading"}
          />

          {/* Right panel */}
          <div className="flex flex-col gap-4">
            {/* Submit validation error (not a connectivity error) */}
            {submitStatus === "error" && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
                {submitError}
              </div>
            )}

            {displayFlow ? (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    {lastResult ? "Latest Classification" : "Selected Flow Detail"}
                  </p>
                  <button
                    onClick={handleOverrideOpen}
                    className="rounded-lg border border-white/10 px-3 py-1 text-xs text-slate-400 transition hover:border-white/30 hover:text-slate-200"
                  >
                    Override classification
                  </button>
                </div>
                <ClassificationCard flow={displayFlow} />
              </div>
            ) : (
              <div className="flex h-full min-h-40 items-center justify-center rounded-2xl border border-white/5 bg-white/[0.02] text-sm text-slate-600">
                Submit a flow or click a row to see the classification detail.
              </div>
            )}
          </div>
        </div>

        {/* ── QoS marking policy (category → DSCP / queue) ── */}
        <QoSPolicyPanel
          policies={qosPolicies}
          activeCategory={displayFlow?.effective_category ?? null}
        />

        {/* ── Flow list (#1 live search, #2 Source badges) ── */}
        <FlowList
          flows={flows}
          selectedId={selectedFlow?.flow_id ?? null}
          onSelect={handleSelect}
          onRefresh={() => void handleRefresh()}
          refreshing={flowsStatus === "loading"}
        />

        {flowsStatus === "error" && (
          <p className="mt-3 text-center text-xs text-rose-400">
            Could not load flows. Is the backend running on localhost:8000?
          </p>
        )}

        {/* ── Status bar (#4) ── */}
        <StatusBar
          flowCount={flows.length}
          lastAction={lastAction}
          lastActionTime={lastActionTime}
        />
      </main>

      {/* Footer */}
      <footer className="relative border-t border-white/5 px-6 py-4 text-center text-xs text-slate-600">
        Frontend: localhost:5173 · Backend: localhost:8000 · Team Mutex ·
        TELIPORT S4
      </footer>

      {/* ── Override modal (#7 warning inside) ── */}
      {showOverride && selectedFlow && (
        <OverrideModal
          flow={selectedFlow}
          onConfirm={(cat, reason) => void handleOverrideConfirm(cat, reason)}
          onCancel={() => setShowOverride(false)}
          loading={overrideStatus === "loading"}
        />
      )}

      {/* ── Toast stack (#3) ── */}
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
