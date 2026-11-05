"""
capacity.py — FastAPI router for Phase 2: Link Capacity Estimator.

Endpoints
---------
GET  /api/capacity          — full estimate (snapshot + breakdown + flows)
GET  /api/capacity/snapshot — aggregate snapshot only (lighter response)
GET  /api/capacity/flows    — per-flow throughput observations only

All values are derived from the submitted flow metadata held in the
in-memory registry.  No live packet capture is performed.
"""

from fastapi import APIRouter, Query

from app.models.capacity import CapacityEstimate, CapacitySnapshot
from app.services.capacity_estimator import (
    DEFAULT_LINK_SPEED_MBPS,
    CapacityEstimator,
)
from app.services.flow_registry import flow_registry

router = APIRouter(prefix="/api/capacity", tags=["capacity"])

# ---------------------------------------------------------------------------
# GET /api/capacity
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=CapacityEstimate,
    summary="Full link capacity estimate",
    description=(
        "Returns the full capacity estimate: an aggregate link snapshot, "
        "per-category bandwidth breakdown, and per-flow throughput detail. "
        "Values are derived from flow metadata submitted to POST /api/flows. "
        "No live packet capture is performed."
    ),
)
def get_capacity_estimate(
    link_speed_mbps: float = Query(
        default=DEFAULT_LINK_SPEED_MBPS,
        gt=0,
        description=(
            "Configured maximum link speed in Mbps used to compute utilisation. "
            "Defaults to 100 Mbps.  Override to match your actual WAN speed."
        ),
    ),
) -> CapacityEstimate:
    estimator = CapacityEstimator(
        registry=flow_registry,
        link_speed_mbps=link_speed_mbps,
    )
    return estimator.estimate()


# ---------------------------------------------------------------------------
# GET /api/capacity/snapshot
# ---------------------------------------------------------------------------


@router.get(
    "/snapshot",
    response_model=CapacitySnapshot,
    summary="Aggregate capacity snapshot",
    description=(
        "Returns the aggregate link snapshot only: total throughput, "
        "utilisation percentage, congestion state and jitter summary. "
        "Lighter than the full estimate — useful for polling dashboards."
    ),
)
def get_capacity_snapshot(
    link_speed_mbps: float = Query(
        default=DEFAULT_LINK_SPEED_MBPS,
        gt=0,
        description="Configured maximum link speed in Mbps.",
    ),
) -> CapacitySnapshot:
    estimator = CapacityEstimator(
        registry=flow_registry,
        link_speed_mbps=link_speed_mbps,
    )
    return estimator.estimate().snapshot
