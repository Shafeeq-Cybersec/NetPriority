"""
test_qos_policy.py — pytest tests for the QoS marking policy layer.

Covers:
- Policy table shape and DSCP validity
- Expected DSCP / queue for every category
- Fallback for unknown category names
- `qos` field present on flow responses
- Override updates the recommendation but preserves the auto result
- GET /api/qos/policies
"""

import pytest
from fastapi.testclient import TestClient

from app.core.qos import QOS_POLICIES, all_policies, policy_for
from app.main import app
from app.models.flow import FlowResponse
from app.services.flow_registry import flow_registry


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


def gaming_flow() -> dict:
    return {
        "src_ip": "192.168.1.50",
        "dst_ip": "203.0.113.10",
        "src_port": 52000,
        "dst_port": 27015,
        "protocol": "UDP",
        "packet_count": 800,
        "byte_count": 160_000,
        "duration_seconds": 30.0,
        "inter_arrival_ms": 15.0,
    }


def minimal_flow() -> dict:
    """Only IPs and protocol — expected: Unknown."""
    return {
        "src_ip": "192.168.1.1",
        "dst_ip": "10.0.0.1",
        "protocol": "TCP",
    }


REQUIRED_POLICY_KEYS = {
    "category",
    "dscp",
    "dscp_class",
    "priority",
    "queue",
    "treatment",
}


# ---------------------------------------------------------------------------
# 1. Policy table
# ---------------------------------------------------------------------------


class TestPolicyTable:
    def test_all_five_categories_have_a_policy(self):
        assert set(QOS_POLICIES) == {
            "Gaming",
            "Video",
            "Signaling",
            "Bulk",
            "Unknown",
        }

    def test_every_policy_has_required_keys(self):
        for policy in all_policies():
            assert REQUIRED_POLICY_KEYS == set(policy)

    def test_every_dscp_is_in_valid_range(self):
        for policy in all_policies():
            assert 0 <= policy["dscp"] <= 63

    def test_gaming_maps_to_expedited_forwarding(self):
        policy = policy_for("Gaming")
        assert policy["dscp"] == 46
        assert policy["dscp_class"] == "EF"
        assert policy["queue"] == "Q1"

    def test_signaling_maps_to_cs5(self):
        policy = policy_for("Signaling")
        assert policy["dscp"] == 40
        assert policy["dscp_class"] == "CS5"

    def test_video_maps_to_af41(self):
        policy = policy_for("Video")
        assert policy["dscp"] == 34
        assert policy["dscp_class"] == "AF41"

    def test_bulk_maps_to_best_effort(self):
        policy = policy_for("Bulk")
        assert policy["dscp"] == 0
        assert policy["dscp_class"] == "CS0"

    def test_unknown_maps_to_best_effort(self):
        policy = policy_for("Unknown")
        assert policy["dscp"] == 0

    def test_unknown_category_name_falls_back_to_default(self):
        assert policy_for("NotARealCategory") == policy_for("Unknown")

    def test_policies_are_ordered_by_dscp_priority(self):
        dscps = [p["dscp"] for p in all_policies()]
        assert dscps == sorted(dscps, reverse=True)

    def test_returned_policy_is_a_copy(self):
        policy = policy_for("Gaming")
        policy["dscp"] = 1
        assert policy_for("Gaming")["dscp"] == 46


# ---------------------------------------------------------------------------
# 2. QoS on flow responses
# ---------------------------------------------------------------------------


class TestFlowQoS:
    def test_submitted_flow_includes_qos(self, client):
        resp = client.post("/api/flows", json=gaming_flow())
        assert resp.status_code == 201
        data = resp.json()
        assert data["qos"]["category"] == "Gaming"
        assert data["qos"]["dscp"] == 46
        assert data["qos"]["queue"] == "Q1"

    def test_unknown_flow_gets_best_effort_qos(self, client):
        resp = client.post("/api/flows", json=minimal_flow())
        assert resp.status_code == 201
        data = resp.json()
        assert data["effective_category"] == "Unknown"
        assert data["qos"]["dscp"] == 0

    def test_list_and_detail_include_qos(self, client):
        flow_id = client.post("/api/flows", json=gaming_flow()).json()["flow_id"]

        listed = client.get("/api/flows").json()[0]
        assert listed["qos"]["dscp"] == 46

        detail = client.get(f"/api/flows/{flow_id}").json()
        assert detail["qos"]["dscp"] == 46

    def test_override_updates_qos_but_not_auto_classification(self, client):
        flow_id = client.post("/api/flows", json=gaming_flow()).json()["flow_id"]

        resp = client.patch(
            f"/api/flows/{flow_id}/classification",
            json={"category": "Bulk", "reason": "Backup job."},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["auto_classification"]["category"] == "Gaming"
        assert data["effective_category"] == "Bulk"
        assert data["qos"]["dscp"] == 0
        assert data["qos"]["category"] == "Bulk"

    def test_flow_response_model_exposes_qos(self, client):
        data = client.post("/api/flows", json=gaming_flow()).json()
        parsed = FlowResponse(**data)
        assert parsed.qos.dscp == 46


# ---------------------------------------------------------------------------
# 3. GET /api/qos/policies
# ---------------------------------------------------------------------------


class TestPoliciesEndpoint:
    def test_returns_all_policies(self, client):
        resp = client.get("/api/qos/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        for item in data:
            assert REQUIRED_POLICY_KEYS.issubset(item.keys())

    def test_policies_ordered_highest_priority_first(self, client):
        data = client.get("/api/qos/policies").json()
        assert data[0]["category"] == "Gaming"
        assert data[-1]["category"] == "Unknown"

    def test_policies_endpoint_does_not_disturb_flow_registry(self, client):
        client.post("/api/flows", json=gaming_flow())
        client.get("/api/qos/policies")
        assert len(client.get("/api/flows").json()) == 1
