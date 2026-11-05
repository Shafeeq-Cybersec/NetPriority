"""
capacity_estimator.py — Phase 2: Link Capacity Estimator.

Architecture
------------
The estimator reads the flow records already stored in the in-memory
registry (FlowRegistry) and derives throughput, utilisation and jitter
estimates from the metadata submitted with each flow.

No live packet capture takes place.  No OS or kernel interfaces are
called.  No private payloads are inspected.  This is explicitly a
*metadata-derived* estimator — it answers "given the flows we have
observed so far, how loaded does the link appear to be?"

Algorithm
---------
1. Iterate all FlowRecord objects in the registry.
2. For each flow that has both byte_count > 0 and duration_seconds > 0,
   compute throughput_bps = (byte_count * 8) / duration_seconds.
3. Sum all per-flow throughputs to get total observed_bps.
4. Compute utilisation_pct = (observed_bps / link_speed_bps) * 100,
   clamped to [0, 100].
5. Classify congestion state from utilisation thresholds.
6. Compute mean and max inter_arrival_ms across flows that reported it.
7. Compute per-category bandwidth breakdown.
8. Return a CapacityEstimate containing the aggregate snapshot,
   per-category breakdown, and per-flow detail.

Thresholds (all configurable via CapacitySettings)
---------------------------------------------------
  CLEAR      : utilisation_pct < 60
  MODERATE   : 60 <= utilisation_pct <= 85
  CONGESTED  : utilisation_pct > 85

Limitations
-----------
- Throughput is per-flow, not per-link direction.
- Flows that overlap in time are summed, not averaged — this overestimates
  utilisation when flows are concurrent.
- Flows without byte_count or duration_seconds contribute to flow count
  but not to bandwidth totals.
- The link speed is a configured value, not auto-detected.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from app.models.capacity import (
    CapacityEstimate,
    CapacitySnapshot,
    CategoryBandwidth,
    CongestionState,
    FlowThroughput,
)
from app.services.flow_registry import FlowRegistry


# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# Default simulated link speed (Mbps).  Represents a typical home broadband
# connection.  Operators can override by passing a different value to
# CapacityEstimator().
DEFAULT_LINK_SPEED_MBPS: float = 100.0

# Congestion thresholds (% utilisation)
THRESHOLD_MODERATE: float = 60.0
THRESHOLD_CONGESTED: float = 85.0


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _bps_to_mbps(bps: float) -> float:
    return round(bps / 1_000_000, 4)


def _compute_flow_bps(byte_count: Optional[int], duration_s: Optional[float]) -> Optional[float]:
    """Return bits-per-second or None when inputs are missing/zero."""
    if (
        byte_count is not None
        and duration_s is not None
        and byte_count > 0
        and duration_s > 0
    ):
        return (byte_count * 8) / duration_s
    return None


def _congestion_state(utilisation_pct: float) -> CongestionState:
    if utilisation_pct > THRESHOLD_CONGESTED:
        return CongestionState.CONGESTED
    if utilisation_pct >= THRESHOLD_MODERATE:
        return CongestionState.MODERATE
    return CongestionState.CLEAR


# ---------------------------------------------------------------------------
# Estimator service
# ---------------------------------------------------------------------------


class CapacityEstimator:
    """
    Stateless capacity estimator.  All data comes from the FlowRegistry.

    Parameters
    ----------
    registry:
        The FlowRegistry instance to read from.
    link_speed_mbps:
        Configured maximum link speed in Mbps.  Defaults to 100 Mbps.
    """

    def __init__(
        self,
        registry: FlowRegistry,
        link_speed_mbps: float = DEFAULT_LINK_SPEED_MBPS,
    ) -> None:
        self._registry = registry
        self._link_speed_mbps = max(link_speed_mbps, 0.001)  # avoid division by zero
        self._link_speed_bps = self._link_speed_mbps * 1_000_000

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate(self) -> CapacityEstimate:
        """
        Compute a full capacity estimate from the current registry state.

        Returns
        -------
        CapacityEstimate
            Aggregate snapshot, per-category breakdown, and per-flow detail.
        """
        records = self._registry.all()

        # --- per-flow throughput ---
        flow_throughputs: list[FlowThroughput] = []
        total_bps: float = 0.0
        jitter_values: list[float] = []
        measurable: int = 0

        for record in records:
            resp = record.to_response()
            bps = _compute_flow_bps(resp.byte_count, resp.duration_seconds)
            if bps is not None:
                total_bps += bps
                measurable += 1

            if resp.inter_arrival_ms is not None:
                jitter_values.append(resp.inter_arrival_ms)

            ft = FlowThroughput(
                flow_id=resp.flow_id,
                src_ip=resp.src_ip,
                dst_ip=resp.dst_ip,
                src_port=resp.src_port,
                dst_port=resp.dst_port,
                protocol=resp.protocol.value,
                effective_category=resp.effective_category.value,
                byte_count=resp.byte_count,
                duration_seconds=resp.duration_seconds,
                inter_arrival_ms=resp.inter_arrival_ms,
                computed_bps=round(bps, 2) if bps is not None else None,
                computed_kbps=round(bps / 1_000, 4) if bps is not None else None,
                computed_mbps=round(bps / 1_000_000, 6) if bps is not None else None,
            )
            flow_throughputs.append(ft)

        # --- aggregate metrics ---
        util = min((total_bps / self._link_speed_bps) * 100, 100.0)
        congestion = _congestion_state(util)
        mean_jitter = (sum(jitter_values) / len(jitter_values)) if jitter_values else None
        max_jitter = max(jitter_values) if jitter_values else None

        snapshot = CapacitySnapshot(
            observed_bps=round(total_bps, 2),
            observed_mbps=_bps_to_mbps(total_bps),
            link_speed_mbps=self._link_speed_mbps,
            utilisation_pct=round(util, 2),
            congestion_state=congestion,
            mean_jitter_ms=round(mean_jitter, 3) if mean_jitter is not None else None,
            max_jitter_ms=round(max_jitter, 3) if max_jitter is not None else None,
            active_flows=len(records),
            measurable_flows=measurable,
            method=(
                "Throughput = sum(byte_count × 8 / duration_seconds) across all "
                "flows with non-zero byte_count and duration_seconds. "
                "Utilisation = observed_bps / configured_link_speed_bps × 100. "
                "Flows without counters are counted but not measured."
            ),
        )

        # --- per-category breakdown ---
        cat_bps: dict[str, float] = defaultdict(float)
        cat_count: dict[str, int] = defaultdict(int)

        for ft in flow_throughputs:
            cat_count[ft.effective_category] += 1
            if ft.computed_bps is not None:
                cat_bps[ft.effective_category] += ft.computed_bps

        by_category: list[CategoryBandwidth] = []
        for cat, count in sorted(cat_count.items()):
            bps_for_cat = cat_bps.get(cat, 0.0)
            share = round((bps_for_cat / total_bps * 100) if total_bps > 0 else 0.0, 2)
            by_category.append(
                CategoryBandwidth(
                    category=cat,
                    flow_count=count,
                    observed_bps=round(bps_for_cat, 2),
                    observed_mbps=_bps_to_mbps(bps_for_cat),
                    share_pct=share,
                )
            )

        return CapacityEstimate(
            snapshot=snapshot,
            by_category=by_category,
            flows=flow_throughputs,
        )

    @property
    def link_speed_mbps(self) -> float:
        return self._link_speed_mbps
