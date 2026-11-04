"""
qos.py — FastAPI router for the QoS marking policy.

Endpoints
---------
GET /api/qos/policies — full category → DSCP / queue policy table

The per-flow recommendation is returned inline on every flow response
(the `qos` field); this endpoint exposes the whole table so operators
and the UI can see how each category is treated.
"""

from fastapi import APIRouter

from app.core.qos import all_policies
from app.models.flow import QoSProfile

router = APIRouter(prefix="/api/qos", tags=["qos"])


@router.get(
    "/policies",
    response_model=list[QoSProfile],
    summary="List the QoS marking policy",
    description=(
        "Returns the category → DSCP / priority tier / queue mapping used "
        "to build the `qos` field on every flow response. "
        "Policies are ordered from highest to lowest priority. "
        "No packets are marked by this phase — these are recommendations "
        "for a future enforcement layer."
    ),
)
def list_qos_policies() -> list[QoSProfile]:
    return [QoSProfile(**policy) for policy in all_policies()]
