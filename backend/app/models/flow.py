"""
Pydantic models for network flow representation and classification.

A "flow" is a 5-tuple (src_ip, src_port, dst_ip, dst_port, protocol)
enriched with traffic statistics observed over its lifetime.

All classification here is metadata-based — no packet payloads are
inspected at any point.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TrafficCategory(str, Enum):
    """Four traffic categories used throughout NetPriority."""

    GAMING = "Gaming"
    VIDEO = "Video"
    SIGNALING = "Signaling"
    BULK = "Bulk"
    UNKNOWN = "Unknown"


class Protocol(str, Enum):
    """Transport-layer protocols supported by the classifier."""

    TCP = "TCP"
    UDP = "UDP"
    OTHER = "Other"


# ---------------------------------------------------------------------------
# Classification result produced by the classifier service
# ---------------------------------------------------------------------------


class ClassificationResult(BaseModel):
    """
    Output of the rule-based classifier.

    confidence_score is an integer in the range 0–100.
    It is a *rule-based heuristic score*, NOT a statistically calibrated
    probability.  It reflects how many independent rules matched the flow
    and how strongly each rule supports the assigned category.
    """

    category: TrafficCategory
    confidence_score: int = Field(
        ge=0,
        le=100,
        description="Rule-based confidence 0–100. Not a calibrated probability.",
    )
    reason: str = Field(
        description="Human-readable explanation of why this category was chosen."
    )
    matched_rules: list[str] = Field(
        default_factory=list,
        description="Names of the classification rules that contributed to this result.",
    )


# ---------------------------------------------------------------------------
# Incoming flow submission (POST /api/flows)
# ---------------------------------------------------------------------------


class FlowSubmit(BaseModel):
    """
    Metadata that the caller submits when registering a new flow.

    All fields except src_ip / dst_ip / protocol are optional so that
    partial observations (e.g. from a passive probe that only sees headers)
    can still be submitted and classified with a lower confidence score.
    """

    src_ip: str = Field(
        description="Source IPv4 or IPv6 address (e.g. '192.168.1.10')."
    )
    dst_ip: str = Field(
        description="Destination IPv4 or IPv6 address."
    )
    src_port: Optional[int] = Field(
        default=None, ge=0, le=65535,
        description="Source port (0–65535).",
    )
    dst_port: Optional[int] = Field(
        default=None, ge=0, le=65535,
        description="Destination port (0–65535).",
    )
    protocol: Protocol = Field(
        default=Protocol.OTHER,
        description="Transport protocol: TCP, UDP, or Other.",
    )
    packet_count: Optional[int] = Field(
        default=None, ge=0,
        description="Total packets observed in this flow.",
    )
    byte_count: Optional[int] = Field(
        default=None, ge=0,
        description="Total bytes observed in this flow.",
    )
    duration_seconds: Optional[float] = Field(
        default=None, ge=0.0,
        description="Flow duration in seconds.",
    )
    mean_packet_size: Optional[float] = Field(
        default=None, ge=0.0,
        description=(
            "Average packet size in bytes. "
            "If not provided it is computed from byte_count / packet_count "
            "when both are available."
        ),
    )
    inter_arrival_ms: Optional[float] = Field(
        default=None, ge=0.0,
        description=(
            "Mean inter-packet arrival time in milliseconds. "
            "Low values suggest real-time or interactive traffic."
        ),
    )

    @field_validator("src_ip", "dst_ip")
    @classmethod
    def ip_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("IP address must not be empty.")
        return v

    @model_validator(mode="after")
    def compute_mean_packet_size(self) -> "FlowSubmit":
        """
        Auto-compute mean_packet_size from byte_count and packet_count
        if the caller did not supply it and both counters are available.
        """
        if (
            self.mean_packet_size is None
            and self.byte_count is not None
            and self.packet_count is not None
            and self.packet_count > 0
        ):
            self.mean_packet_size = self.byte_count / self.packet_count
        return self


# ---------------------------------------------------------------------------
# Full flow record stored in the registry
# ---------------------------------------------------------------------------


class FlowRecord(BaseModel):
    """
    Complete flow record as stored in the in-memory registry.

    Combines the submitted metadata, the automatic classification, and
    any manual override applied by an administrator.
    """

    flow_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this flow.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the flow was registered.",
    )

    # --- submitted metadata ---
    src_ip: str
    dst_ip: str
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Protocol = Protocol.OTHER
    packet_count: Optional[int] = None
    byte_count: Optional[int] = None
    duration_seconds: Optional[float] = None
    mean_packet_size: Optional[float] = None
    inter_arrival_ms: Optional[float] = None

    # --- automatic classification ---
    auto_classification: ClassificationResult

    # --- manual override (None = not overridden) ---
    manual_category: Optional[TrafficCategory] = None
    manual_override_reason: Optional[str] = None
    is_manually_overridden: bool = False

    @property
    def effective_category(self) -> TrafficCategory:
        """
        Return the currently active category.
        Returns the manual override if set, otherwise the automatic result.
        """
        if self.is_manually_overridden and self.manual_category is not None:
            return self.manual_category
        return self.auto_classification.category

    def to_response(self) -> "FlowResponse":
        """Convert to the response schema sent to API callers."""
        return FlowResponse(
            flow_id=self.flow_id,
            created_at=self.created_at,
            src_ip=self.src_ip,
            dst_ip=self.dst_ip,
            src_port=self.src_port,
            dst_port=self.dst_port,
            protocol=self.protocol,
            packet_count=self.packet_count,
            byte_count=self.byte_count,
            duration_seconds=self.duration_seconds,
            mean_packet_size=self.mean_packet_size,
            inter_arrival_ms=self.inter_arrival_ms,
            auto_classification=self.auto_classification,
            manual_category=self.manual_category,
            manual_override_reason=self.manual_override_reason,
            is_manually_overridden=self.is_manually_overridden,
            effective_category=self.effective_category,
        )


# ---------------------------------------------------------------------------
# API response schema
# ---------------------------------------------------------------------------


class FlowResponse(BaseModel):
    """Schema returned by GET /api/flows and POST /api/flows."""

    flow_id: str
    created_at: datetime
    src_ip: str
    dst_ip: str
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Protocol
    packet_count: Optional[int] = None
    byte_count: Optional[int] = None
    duration_seconds: Optional[float] = None
    mean_packet_size: Optional[float] = None
    inter_arrival_ms: Optional[float] = None
    auto_classification: ClassificationResult
    manual_category: Optional[TrafficCategory] = None
    manual_override_reason: Optional[str] = None
    is_manually_overridden: bool
    effective_category: TrafficCategory


# ---------------------------------------------------------------------------
# Manual override request (PATCH /api/flows/{flow_id}/classification)
# ---------------------------------------------------------------------------


class ClassificationOverride(BaseModel):
    """Request body for a manual classification override."""

    category: TrafficCategory = Field(
        description="The corrected traffic category chosen by the administrator."
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional human-readable reason for the correction.",
    )

    @field_validator("category")
    @classmethod
    def category_not_unknown(cls, v: TrafficCategory) -> TrafficCategory:
        if v == TrafficCategory.UNKNOWN:
            raise ValueError(
                "Cannot manually set category to Unknown. "
                "Choose Gaming, Video, Signaling, or Bulk."
            )
        return v
