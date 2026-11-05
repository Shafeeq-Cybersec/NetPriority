"""
capacity.py — Pydantic models for Phase 2: Link Capacity Estimator.

All estimates are derived from flow metadata already held in the in-memory
registry.  No live packet capture, no OS calls and no payload inspection
take place in Phase 2 — those belong to Phase 3 (tc enforcement).

The estimates are clearly labelled as *derived* values so callers know they
reflect the last submitted batch of flows, not a real-time wire measurement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class CongestionState(str, Enum):
    """Simple three-state congestion indicator derived from utilisation."""

    CLEAR = "clear"           # < 60 % utilisation
    MODERATE = "moderate"     # 60 – 85 % utilisation
    CONGESTED = "congested"   # > 85 % utilisation


# ---------------------------------------------------------------------------
# Per-flow throughput observation
# ---------------------------------------------------------------------------


class FlowThroughput(BaseModel):
    """
    Throughput estimate for a single observed flow.

    computed_bps is derived as byte_count / duration_seconds * 8.
    If duration_seconds is zero or unavailable, computed_bps is None.
    """

    flow_id: str
    src_ip: str
    dst_ip: str
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: str
    effective_category: str

    # Raw counters from the submitted flow
    byte_count: Optional[int] = None
    duration_seconds: Optional[float] = None

    # Derived
    computed_bps: Optional[float] = Field(
        default=None,
        description="Estimated throughput in bits per second (byte_count / duration × 8).",
    )
    computed_kbps: Optional[float] = Field(
        default=None,
        description="computed_bps / 1000 — kilobits per second.",
    )
    computed_mbps: Optional[float] = Field(
        default=None,
        description="computed_bps / 1_000_000 — megabits per second.",
    )

    # Inter-arrival jitter proxy
    inter_arrival_ms: Optional[float] = Field(
        default=None,
        description="Mean inter-packet arrival time submitted with the flow (ms).",
    )


# ---------------------------------------------------------------------------
# Link capacity snapshot
# ---------------------------------------------------------------------------


class CapacitySnapshot(BaseModel):
    """
    Aggregate link capacity estimate derived from all flows in the registry.

    Fields:
        observed_bps        — sum of computed_bps for all flows with counters.
        observed_mbps       — observed_bps / 1_000_000.
        link_speed_mbps     — configured maximum link speed (from settings).
        utilisation_pct     — (observed_bps / link_speed_bps) * 100, capped at 100.
        congestion_state    — CLEAR / MODERATE / CONGESTED threshold classification.
        mean_jitter_ms      — mean of all submitted inter_arrival_ms values.
        max_jitter_ms       — maximum inter_arrival_ms across all flows.
        active_flows        — number of flows that contributed to the estimate.
        measurable_flows    — flows with enough metadata (byte_count + duration).
        estimated_at        — UTC timestamp of this snapshot.
        method              — brief note explaining the derivation method.

    Limitation note (returned in every response):
        These values are derived from manually submitted flow metadata, not
        from live wire measurements.  They reflect the flows registered in
        the current in-memory session only.
    """

    observed_bps: float = Field(
        description="Total observed throughput in bits per second across all measured flows."
    )
    observed_mbps: float = Field(
        description="observed_bps expressed in Mbps."
    )
    link_speed_mbps: float = Field(
        description="Configured maximum link speed in Mbps (set in backend config)."
    )
    utilisation_pct: float = Field(
        ge=0.0, le=100.0,
        description="Percentage of configured link speed currently observed in use.",
    )
    congestion_state: CongestionState = Field(
        description="CLEAR (<60%), MODERATE (60–85%) or CONGESTED (>85%)."
    )
    mean_jitter_ms: Optional[float] = Field(
        default=None,
        description="Mean inter-packet arrival time across all flows that reported it.",
    )
    max_jitter_ms: Optional[float] = Field(
        default=None,
        description="Maximum inter-arrival time seen across all flows.",
    )
    active_flows: int = Field(
        description="Total number of flows currently in the registry."
    )
    measurable_flows: int = Field(
        description="Flows with enough metadata (byte_count + duration_seconds) to compute throughput."
    )
    estimated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when this snapshot was computed.",
    )
    method: str = Field(
        description="Brief description of the derivation method."
    )
    limitation: str = Field(
        default=(
            "Derived from submitted flow metadata only. "
            "Not a live wire measurement. "
            "Reflects the current in-memory session."
        ),
        description="Disclaimer about the accuracy of these estimates.",
    )


# ---------------------------------------------------------------------------
# Per-category breakdown
# ---------------------------------------------------------------------------


class CategoryBandwidth(BaseModel):
    """Bandwidth usage broken down by traffic category."""

    category: str
    flow_count: int
    observed_bps: float
    observed_mbps: float
    share_pct: float = Field(
        description="This category's share of the total observed bandwidth (%)."
    )


# ---------------------------------------------------------------------------
# Full estimation response
# ---------------------------------------------------------------------------


class CapacityEstimate(BaseModel):
    """
    Full Phase 2 link capacity estimation response.

    Combines the aggregate snapshot, per-category breakdown, and per-flow
    throughput observations in a single response.
    """

    snapshot: CapacitySnapshot
    by_category: list[CategoryBandwidth]
    flows: list[FlowThroughput]
