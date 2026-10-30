"""
flows.py — FastAPI router for Phase 1 traffic classification endpoints.

Endpoints
---------
GET  /api/flows                            — list all observed flows
POST /api/flows                            — submit and classify a new flow
GET  /api/flows/{flow_id}                  — retrieve one flow
PATCH /api/flows/{flow_id}/classification  — manually override classification
"""

from fastapi import APIRouter, HTTPException, status

from app.models.flow import (
    ClassificationOverride,
    FlowRecord,
    FlowResponse,
    FlowSubmit,
    TrafficCategory,
)
from app.services.classifier_service import ClassifierService
from app.services.flow_registry import flow_registry

router = APIRouter(prefix="/api/flows", tags=["classifier"])

# One shared classifier instance (stateless — safe to reuse).
_classifier = ClassifierService()


# ---------------------------------------------------------------------------
# GET /api/flows
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[FlowResponse],
    summary="List all observed flows",
    description=(
        "Returns every flow currently held in the in-memory registry, "
        "ordered by submission time (oldest first). "
        "Each flow includes its metadata, automatic classification, "
        "and any manual override applied by an administrator."
    ),
)
def list_flows() -> list[FlowResponse]:
    return [r.to_response() for r in flow_registry.all()]


# ---------------------------------------------------------------------------
# POST /api/flows
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=FlowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a flow for classification",
    description=(
        "Accept flow metadata, validate it, classify it using the "
        "metadata-based rule engine, store it in the in-memory registry, "
        "and return the full classification result. "
        "No packet payloads are inspected."
    ),
)
def submit_flow(body: FlowSubmit) -> FlowResponse:
    result = _classifier.classify(body)

    record = FlowRecord(
        src_ip=body.src_ip,
        dst_ip=body.dst_ip,
        src_port=body.src_port,
        dst_port=body.dst_port,
        protocol=body.protocol,
        packet_count=body.packet_count,
        byte_count=body.byte_count,
        duration_seconds=body.duration_seconds,
        mean_packet_size=body.mean_packet_size,
        inter_arrival_ms=body.inter_arrival_ms,
        auto_classification=result,
    )

    flow_registry.add(record)
    return record.to_response()


# ---------------------------------------------------------------------------
# GET /api/flows/{flow_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{flow_id}",
    response_model=FlowResponse,
    summary="Retrieve a single flow",
    description="Returns one flow record identified by its UUID flow_id.",
)
def get_flow(flow_id: str) -> FlowResponse:
    record = flow_registry.get(flow_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow '{flow_id}' not found.",
        )
    return record.to_response()


# ---------------------------------------------------------------------------
# PATCH /api/flows/{flow_id}/classification
# ---------------------------------------------------------------------------


@router.patch(
    "/{flow_id}/classification",
    response_model=FlowResponse,
    summary="Manually override a flow's classification",
    description=(
        "Allows an administrator to correct a misclassification. "
        "The original automatic classification is always preserved for "
        "comparison; this endpoint only sets the manual_category field. "
        "The effective_category in the response will reflect the override. "
        "Category must be Gaming, Video, Signaling, or Bulk — Unknown is not allowed."
    ),
)
def override_classification(
    flow_id: str,
    body: ClassificationOverride,
) -> FlowResponse:
    record = flow_registry.get(flow_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow '{flow_id}' not found.",
        )

    # Apply override — we rebuild the record with updated fields.
    # FlowRecord is a Pydantic model so we use model_copy.
    updated = record.model_copy(
        update={
            "manual_category": body.category,
            "manual_override_reason": body.reason or "Manually overridden by administrator.",
            "is_manually_overridden": True,
        }
    )

    flow_registry.update(updated)
    return updated.to_response()
