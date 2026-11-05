/**
 * Thin API client for talking to the NetPriority FastAPI backend.
 *
 * The base URL can be overridden with a Vite env var (VITE_API_BASE) but
 * defaults to the local backend at http://localhost:8000.
 */

export interface ProjectInfo {
  name: string;
  description: string;
  version: string;
  status: string;
}

export interface HealthStatus {
  status: string;
  service: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Phase 1 — Traffic Classifier types
// ---------------------------------------------------------------------------

export type TrafficCategory =
  | "Gaming"
  | "Video"
  | "Signaling"
  | "Bulk"
  | "Unknown";

export type Protocol = "TCP" | "UDP" | "Other";

export interface ClassificationResult {
  category: TrafficCategory;
  confidence_score: number;
  reason: string;
  matched_rules: string[];
}

export interface QoSProfile {
  category: TrafficCategory;
  dscp: number;
  dscp_class: string;
  priority: string;
  queue: string;
  treatment: string;
}

export interface FlowResponse {
  flow_id: string;
  created_at: string;
  src_ip: string;
  dst_ip: string;
  src_port: number | null;
  dst_port: number | null;
  protocol: Protocol;
  packet_count: number | null;
  byte_count: number | null;
  duration_seconds: number | null;
  mean_packet_size: number | null;
  inter_arrival_ms: number | null;
  auto_classification: ClassificationResult;
  manual_category: TrafficCategory | null;
  manual_override_reason: string | null;
  is_manually_overridden: boolean;
  effective_category: TrafficCategory;
  qos: QoSProfile;
}

export interface FlowSubmit {
  src_ip: string;
  dst_ip: string;
  src_port?: number | null;
  dst_port?: number | null;
  protocol?: Protocol;
  packet_count?: number | null;
  byte_count?: number | null;
  duration_seconds?: number | null;
  mean_packet_size?: number | null;
  inter_arrival_ms?: number | null;
}

export interface ClassificationOverride {
  category: TrafficCategory;
  reason?: string;
}

// ---------------------------------------------------------------------------
// Core fetch helper
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    // Try to extract FastAPI's detail message
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json() as { detail?: string | { msg: string }[] };
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        detail = body.detail.map((d) => d.msg).join(", ");
      }
    } catch { /* ignore parse errors */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Existing endpoints
// ---------------------------------------------------------------------------

export function getProjectInfo(): Promise<ProjectInfo> {
  return request<ProjectInfo>("/");
}

export function getHealthStatus(): Promise<HealthStatus> {
  return request<HealthStatus>("/api/health");
}

// ---------------------------------------------------------------------------
// Phase 1 — Flow Classifier endpoints
// ---------------------------------------------------------------------------

/** GET /api/flows — list all classified flows */
export function listFlows(): Promise<FlowResponse[]> {
  return request<FlowResponse[]>("/api/flows");
}

/** POST /api/flows — submit flow metadata, receive classification */
export function submitFlow(body: FlowSubmit): Promise<FlowResponse> {
  return request<FlowResponse>("/api/flows", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** GET /api/flows/:id — retrieve a single flow */
export function getFlow(flowId: string): Promise<FlowResponse> {
  return request<FlowResponse>(`/api/flows/${flowId}`);
}

/** GET /api/qos/policies — category → DSCP / queue policy table */
export function listQoSPolicies(): Promise<QoSProfile[]> {
  return request<QoSProfile[]>("/api/qos/policies");
}

// ---------------------------------------------------------------------------
// Phase 2 — Link Capacity Estimator types and endpoints
// ---------------------------------------------------------------------------

export type CongestionState = "clear" | "moderate" | "congested";

export interface FlowThroughput {
  flow_id: string;
  src_ip: string;
  dst_ip: string;
  src_port: number | null;
  dst_port: number | null;
  protocol: string;
  effective_category: string;
  byte_count: number | null;
  duration_seconds: number | null;
  computed_bps: number | null;
  computed_kbps: number | null;
  computed_mbps: number | null;
  inter_arrival_ms: number | null;
}

export interface CapacitySnapshot {
  observed_bps: number;
  observed_mbps: number;
  link_speed_mbps: number;
  utilisation_pct: number;
  congestion_state: CongestionState;
  mean_jitter_ms: number | null;
  max_jitter_ms: number | null;
  active_flows: number;
  measurable_flows: number;
  estimated_at: string;
  method: string;
  limitation: string;
}

export interface CategoryBandwidth {
  category: string;
  flow_count: number;
  observed_bps: number;
  observed_mbps: number;
  share_pct: number;
}

export interface CapacityEstimate {
  snapshot: CapacitySnapshot;
  by_category: CategoryBandwidth[];
  flows: FlowThroughput[];
}

/** GET /api/capacity — full estimate (snapshot + breakdown + per-flow) */
export function getCapacityEstimate(
  linkSpeedMbps?: number,
): Promise<CapacityEstimate> {
  const qs = linkSpeedMbps != null ? `?link_speed_mbps=${linkSpeedMbps}` : "";
  return request<CapacityEstimate>(`/api/capacity${qs}`);
}

/** GET /api/capacity/snapshot — aggregate snapshot only */
export function getCapacitySnapshot(
  linkSpeedMbps?: number,
): Promise<CapacitySnapshot> {
  const qs = linkSpeedMbps != null ? `?link_speed_mbps=${linkSpeedMbps}` : "";
  return request<CapacitySnapshot>(`/api/capacity/snapshot${qs}`);
}

/** PATCH /api/flows/:id/classification — manually override classification */
export function overrideClassification(
  flowId: string,
  body: ClassificationOverride,
): Promise<FlowResponse> {
  return request<FlowResponse>(`/api/flows/${flowId}/classification`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}
