"""
test_classifier.py — pytest test suite for Phase 1: Traffic Classifier.

Covers:
- Gaming classification
- Video classification
- Signaling classification
- Bulk classification
- Unknown / insufficient metadata
- Invalid flow input (validation errors)
- GET /api/flows  — flow listing
- GET /api/flows/{flow_id}  — individual retrieval
- POST /api/flows  — flow submission
- PATCH /api/flows/{flow_id}/classification  — manual override
- Invalid manual classification (Unknown not allowed)
- Original classification preserved after manual override

The TestClient from httpx drives a real FastAPI ASGI app so that request
validation, routing and response serialisation are all exercised.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.classifier_service import ClassifierService
from app.services.flow_registry import flow_registry
from app.models.flow import FlowSubmit, Protocol, TrafficCategory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_registry():
    """Reset the in-memory registry before every test."""
    flow_registry.clear()
    yield
    flow_registry.clear()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def classifier():
    return ClassifierService()


# ---------------------------------------------------------------------------
# Helper — build a minimal flow dict for the POST endpoint
# ---------------------------------------------------------------------------


def gaming_flow() -> dict:
    """UDP, low inter-arrival, small packets — expected: Gaming."""
    return {
        "src_ip": "192.168.1.50",
        "dst_ip": "203.0.113.10",
        "src_port": 52000,
        "dst_port": 27015,          # Steam game server port
        "protocol": "UDP",
        "packet_count": 800,
        "byte_count": 160_000,      # 200 bytes/pkt mean
        "duration_seconds": 30.0,
        "inter_arrival_ms": 15.0,   # very low — real-time updates
    }


def video_flow() -> dict:
    """UDP, large packets, high byte rate — expected: Video (RTP-like)."""
    return {
        "src_ip": "198.51.100.1",
        "dst_ip": "192.168.1.100",
        "src_port": 5004,
        "dst_port": 5004,           # RTP video port
        "protocol": "UDP",
        "packet_count": 2000,
        "byte_count": 20_000_000,   # 10 000 bytes/pkt mean → large
        "duration_seconds": 20.0,
        "inter_arrival_ms": 10.0,
    }


def signaling_flow() -> dict:
    """UDP to SIP port, tiny packets, low rate — expected: Signaling."""
    return {
        "src_ip": "10.0.0.5",
        "dst_ip": "10.0.0.1",
        "src_port": 60000,
        "dst_port": 5060,           # SIP
        "protocol": "UDP",
        "packet_count": 20,
        "byte_count": 2_000,        # 100 bytes/pkt
        "duration_seconds": 5.0,
        "inter_arrival_ms": 250.0,
    }


def bulk_flow() -> dict:
    """TCP, near-MTU packets, very high byte rate, long — expected: Bulk."""
    return {
        "src_ip": "192.168.1.20",
        "dst_ip": "185.60.219.35",
        "src_port": 54321,
        "dst_port": 445,            # SMB
        "protocol": "TCP",
        "packet_count": 5000,
        "byte_count": 70_000_000,   # 14 000 bytes/pkt mean
        "duration_seconds": 30.0,
    }


# ---------------------------------------------------------------------------
# 1. Unit tests — ClassifierService directly
# ---------------------------------------------------------------------------


class TestClassifierServiceGaming:
    def test_gaming_known_port_low_inter_arrival(self, classifier):
        flow = FlowSubmit(**gaming_flow())
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.GAMING
        assert result.confidence_score >= 20
        assert len(result.matched_rules) > 0
        assert "Gaming" in result.reason

    def test_gaming_small_udp_packet_no_port(self, classifier):
        """Small UDP packets without a well-known port should still lean Gaming."""
        flow = FlowSubmit(
            src_ip="192.168.1.5",
            dst_ip="1.2.3.4",
            src_port=50000,
            dst_port=9999,   # not a known gaming port
            protocol=Protocol.UDP,
            packet_count=500,
            byte_count=100_000,   # 200 bytes/pkt
            duration_seconds=20.0,
            inter_arrival_ms=12.0,
        )
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.GAMING
        assert result.confidence_score >= 20

    def test_gaming_reason_is_human_readable(self, classifier):
        flow = FlowSubmit(**gaming_flow())
        result = classifier.classify(flow)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 20


class TestClassifierServiceVideo:
    def test_video_rtp_port(self, classifier):
        flow = FlowSubmit(**video_flow())
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.VIDEO
        assert result.confidence_score >= 20
        assert "Video" in result.reason

    def test_video_rtsp_port(self, classifier):
        flow = FlowSubmit(
            src_ip="203.0.113.5",
            dst_ip="192.168.1.10",
            src_port=554,
            dst_port=554,       # RTSP
            protocol=Protocol.TCP,
            packet_count=1000,
            byte_count=5_000_000,
            duration_seconds=60.0,
        )
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.VIDEO
        assert result.confidence_score >= 20

    def test_video_high_throughput_tcp(self, classifier):
        """Long-lived TCP, high byte rate, large packets → Video."""
        flow = FlowSubmit(
            src_ip="203.0.113.99",
            dst_ip="192.168.1.50",
            src_port=443,
            dst_port=443,
            protocol=Protocol.TCP,
            packet_count=10000,
            byte_count=60_000_000,   # 6 MB/s over 10 s
            duration_seconds=10.0,
            mean_packet_size=1000.0,
        )
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.VIDEO
        assert result.confidence_score >= 20


class TestClassifierServiceSignaling:
    def test_signaling_sip(self, classifier):
        flow = FlowSubmit(**signaling_flow())
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.SIGNALING
        assert result.confidence_score >= 20
        assert "Signaling" in result.reason

    def test_signaling_stun(self, classifier):
        flow = FlowSubmit(
            src_ip="10.0.0.2",
            dst_ip="216.93.246.18",
            src_port=55000,
            dst_port=3478,      # STUN
            protocol=Protocol.UDP,
            packet_count=6,
            byte_count=480,     # 80 bytes/pkt
            duration_seconds=1.0,
        )
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.SIGNALING
        assert result.confidence_score >= 20

    def test_signaling_small_packets_low_rate(self, classifier):
        """No known port but tiny packets and very low rate → Signaling."""
        flow = FlowSubmit(
            src_ip="10.0.0.3",
            dst_ip="10.0.0.1",
            src_port=60001,
            dst_port=9999,
            protocol=Protocol.UDP,
            packet_count=10,
            byte_count=1_000,   # 100 bytes/pkt, 200 B/s
            duration_seconds=5.0,
        )
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.SIGNALING
        assert result.confidence_score >= 20


class TestClassifierServiceBulk:
    def test_bulk_smb_port(self, classifier):
        flow = FlowSubmit(**bulk_flow())
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.BULK
        assert result.confidence_score >= 20
        assert "Bulk" in result.reason

    def test_bulk_ftp(self, classifier):
        flow = FlowSubmit(
            src_ip="192.168.1.30",
            dst_ip="10.0.0.100",
            src_port=45000,
            dst_port=21,        # FTP control
            protocol=Protocol.TCP,
            packet_count=200,
            byte_count=500_000,
            duration_seconds=10.0,
        )
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.BULK

    def test_bulk_bittorrent_range(self, classifier):
        flow = FlowSubmit(
            src_ip="192.168.1.40",
            dst_ip="5.5.5.5",
            src_port=50000,
            dst_port=6882,      # BitTorrent range 6881-6889
            protocol=Protocol.TCP,
            packet_count=3000,
            byte_count=30_000_000,
            duration_seconds=40.0,
        )
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.BULK

    def test_bulk_large_long_flow(self, classifier):
        """Near-MTU packets, many packets, long duration, no known port."""
        flow = FlowSubmit(
            src_ip="192.168.1.60",
            dst_ip="8.8.8.8",
            src_port=55000,
            dst_port=8080,
            protocol=Protocol.TCP,
            packet_count=2000,
            byte_count=2_800_000,   # 1400 bytes/pkt
            duration_seconds=60.0,
        )
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.BULK


class TestClassifierServiceUnknown:
    def test_unknown_minimal_metadata(self, classifier):
        """Only IPs and protocol provided — not enough to classify."""
        flow = FlowSubmit(
            src_ip="192.168.1.1",
            dst_ip="10.0.0.1",
            protocol=Protocol.TCP,
        )
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.UNKNOWN
        assert result.confidence_score == 0

    def test_unknown_high_port_no_stats(self, classifier):
        """Ephemeral port, no stats → ambiguous."""
        flow = FlowSubmit(
            src_ip="192.168.1.2",
            dst_ip="203.0.113.1",
            src_port=54321,
            dst_port=54322,
            protocol=Protocol.TCP,
        )
        result = classifier.classify(flow)
        assert result.category == TrafficCategory.UNKNOWN
        assert result.confidence_score == 0

    def test_unknown_has_reason_text(self, classifier):
        flow = FlowSubmit(
            src_ip="1.1.1.1",
            dst_ip="2.2.2.2",
            protocol=Protocol.OTHER,
        )
        result = classifier.classify(flow)
        assert result.reason
        assert len(result.reason) > 10


# ---------------------------------------------------------------------------
# 2. API integration tests — via TestClient
# ---------------------------------------------------------------------------


class TestPostFlow:
    def test_submit_gaming_flow(self, client):
        resp = client.post("/api/flows", json=gaming_flow())
        assert resp.status_code == 201
        data = resp.json()
        assert data["auto_classification"]["category"] == "Gaming"
        assert "flow_id" in data
        assert data["is_manually_overridden"] is False
        assert data["effective_category"] == "Gaming"

    def test_submit_video_flow(self, client):
        resp = client.post("/api/flows", json=video_flow())
        assert resp.status_code == 201
        assert resp.json()["auto_classification"]["category"] == "Video"

    def test_submit_signaling_flow(self, client):
        resp = client.post("/api/flows", json=signaling_flow())
        assert resp.status_code == 201
        assert resp.json()["auto_classification"]["category"] == "Signaling"

    def test_submit_bulk_flow(self, client):
        resp = client.post("/api/flows", json=bulk_flow())
        assert resp.status_code == 201
        assert resp.json()["auto_classification"]["category"] == "Bulk"

    def test_submit_returns_confidence_and_reason(self, client):
        resp = client.post("/api/flows", json=gaming_flow())
        data = resp.json()
        assert data["auto_classification"]["confidence_score"] >= 0
        assert isinstance(data["auto_classification"]["reason"], str)
        assert len(data["auto_classification"]["reason"]) > 0

    def test_submit_returns_matched_rules(self, client):
        resp = client.post("/api/flows", json=gaming_flow())
        data = resp.json()
        assert isinstance(data["auto_classification"]["matched_rules"], list)

    def test_invalid_missing_src_ip(self, client):
        bad = gaming_flow()
        del bad["src_ip"]
        resp = client.post("/api/flows", json=bad)
        assert resp.status_code == 422

    def test_invalid_missing_dst_ip(self, client):
        bad = gaming_flow()
        del bad["dst_ip"]
        resp = client.post("/api/flows", json=bad)
        assert resp.status_code == 422

    def test_invalid_port_out_of_range(self, client):
        bad = gaming_flow()
        bad["dst_port"] = 99999   # > 65535
        resp = client.post("/api/flows", json=bad)
        assert resp.status_code == 422

    def test_invalid_negative_byte_count(self, client):
        bad = gaming_flow()
        bad["byte_count"] = -1
        resp = client.post("/api/flows", json=bad)
        assert resp.status_code == 422

    def test_invalid_empty_src_ip(self, client):
        bad = gaming_flow()
        bad["src_ip"] = "   "
        resp = client.post("/api/flows", json=bad)
        assert resp.status_code == 422

    def test_invalid_bad_protocol(self, client):
        bad = gaming_flow()
        bad["protocol"] = "ICMP"
        resp = client.post("/api/flows", json=bad)
        assert resp.status_code == 422


class TestGetFlows:
    def test_empty_list_initially(self, client):
        resp = client.get("/api/flows")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_contains_submitted_flow(self, client):
        client.post("/api/flows", json=gaming_flow())
        resp = client.get("/api/flows")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_multiple_flows(self, client):
        client.post("/api/flows", json=gaming_flow())
        client.post("/api/flows", json=video_flow())
        client.post("/api/flows", json=signaling_flow())
        resp = client.get("/api/flows")
        assert len(resp.json()) == 3

    def test_list_response_schema(self, client):
        client.post("/api/flows", json=gaming_flow())
        item = client.get("/api/flows").json()[0]
        required_keys = {
            "flow_id", "created_at", "src_ip", "dst_ip",
            "auto_classification", "effective_category",
            "is_manually_overridden",
        }
        assert required_keys.issubset(item.keys())


class TestGetSingleFlow:
    def test_get_existing_flow(self, client):
        post_resp = client.post("/api/flows", json=gaming_flow())
        flow_id = post_resp.json()["flow_id"]
        get_resp = client.get(f"/api/flows/{flow_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["flow_id"] == flow_id

    def test_get_nonexistent_flow_returns_404(self, client):
        resp = client.get("/api/flows/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_get_flow_data_matches_submitted(self, client):
        post_resp = client.post("/api/flows", json=gaming_flow())
        flow_id = post_resp.json()["flow_id"]
        get_resp = client.get(f"/api/flows/{flow_id}")
        data = get_resp.json()
        assert data["src_ip"] == "192.168.1.50"
        assert data["dst_port"] == 27015
        assert data["protocol"] == "UDP"


class TestManualOverride:
    def test_override_changes_effective_category(self, client):
        post_resp = client.post("/api/flows", json=gaming_flow())
        flow_id = post_resp.json()["flow_id"]

        patch_resp = client.patch(
            f"/api/flows/{flow_id}/classification",
            json={"category": "Bulk", "reason": "Actually a download."},
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["manual_category"] == "Bulk"
        assert data["effective_category"] == "Bulk"
        assert data["is_manually_overridden"] is True

    def test_original_classification_preserved_after_override(self, client):
        """auto_classification must not be mutated by the override."""
        post_resp = client.post("/api/flows", json=gaming_flow())
        original_category = post_resp.json()["auto_classification"]["category"]
        flow_id = post_resp.json()["flow_id"]

        client.patch(
            f"/api/flows/{flow_id}/classification",
            json={"category": "Video"},
        )

        get_resp = client.get(f"/api/flows/{flow_id}")
        data = get_resp.json()
        # Auto classification is unchanged
        assert data["auto_classification"]["category"] == original_category
        # But effective is the manual one
        assert data["effective_category"] == "Video"
        assert data["is_manually_overridden"] is True

    def test_override_reason_stored(self, client):
        post_resp = client.post("/api/flows", json=gaming_flow())
        flow_id = post_resp.json()["flow_id"]
        client.patch(
            f"/api/flows/{flow_id}/classification",
            json={"category": "Signaling", "reason": "VoIP call detected by operator."},
        )
        data = client.get(f"/api/flows/{flow_id}").json()
        assert "VoIP" in data["manual_override_reason"]

    def test_override_without_reason_still_works(self, client):
        post_resp = client.post("/api/flows", json=video_flow())
        flow_id = post_resp.json()["flow_id"]
        resp = client.patch(
            f"/api/flows/{flow_id}/classification",
            json={"category": "Bulk"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_manually_overridden"] is True

    def test_invalid_override_unknown_category(self, client):
        """Setting category to Unknown must be rejected (422)."""
        post_resp = client.post("/api/flows", json=gaming_flow())
        flow_id = post_resp.json()["flow_id"]
        resp = client.patch(
            f"/api/flows/{flow_id}/classification",
            json={"category": "Unknown"},
        )
        assert resp.status_code == 422

    def test_invalid_override_bad_category_string(self, client):
        post_resp = client.post("/api/flows", json=gaming_flow())
        flow_id = post_resp.json()["flow_id"]
        resp = client.patch(
            f"/api/flows/{flow_id}/classification",
            json={"category": "Torrenting"},
        )
        assert resp.status_code == 422

    def test_override_nonexistent_flow_returns_404(self, client):
        resp = client.patch(
            "/api/flows/00000000-0000-0000-0000-000000000000/classification",
            json={"category": "Gaming"},
        )
        assert resp.status_code == 404

    def test_second_override_replaces_first(self, client):
        post_resp = client.post("/api/flows", json=gaming_flow())
        flow_id = post_resp.json()["flow_id"]
        client.patch(f"/api/flows/{flow_id}/classification", json={"category": "Video"})
        client.patch(f"/api/flows/{flow_id}/classification", json={"category": "Signaling"})
        data = client.get(f"/api/flows/{flow_id}").json()
        assert data["effective_category"] == "Signaling"
