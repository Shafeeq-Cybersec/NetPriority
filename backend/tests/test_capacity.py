"""
test_capacity.py — pytest test suite for Phase 2: Link Capacity Estimator.

Covers:
  - Empty registry → zero throughput, CLEAR congestion state
  - Single flow with counters → correct bps/mbps/utilisation
  - Multiple flows → sum of throughputs
  - Flow without byte_count → counted but not measured
  - Flow without duration_seconds → counted but not measured
  - Utilisation percentage capped at 100 %
  - CLEAR / MODERATE / CONGESTED thresholds
  - Jitter (mean, max) derived from inter_arrival_ms
  - Per-category breakdown totals
  - GET /api/capacity endpoint
  - GET /api/capacity/snapshot endpoint
  - link_speed_mbps query parameter changes utilisation
  - Existing Phase 1 tests unaffected (flow registry cleared between tests)
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.capacity import CongestionState
from app.services.capacity_estimator import (
    THRESHOLD_CONGESTED,
    THRESHOLD_MODERATE,
    CapacityEstimator,
)
from app.services.flow_registry import flow_registry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_registry():
    flow_registry.clear()
    yield
    flow_registry.clear()


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Flow helpers
# ---------------------------------------------------------------------------

def _submit(client, **overrides) -> dict:
    """POST a flow to the API and return the response JSON."""
    base = {
        "src_ip": "192.168.1.10",
        "dst_ip": "203.0.113.1",
        "protocol": "TCP",
    }
    base.update(overrides)
    resp = client.post("/api/flows", json=base)
    assert resp.status_code == 201
    return resp.json()


def _gaming_flow(client) -> dict:
    return _submit(
        client,
        src_ip="192.168.1.50",
        dst_ip="203.0.113.10",
        src_port=52000,
        dst_port=27015,
        protocol="UDP",
        packet_count=800,
        byte_count=160_000,
        duration_seconds=30.0,
        inter_arrival_ms=15.0,
    )


def _bulk_flow(client, byte_count=70_000_000, duration_seconds=30.0) -> dict:
    return _submit(
        client,
        src_ip="192.168.1.20",
        dst_ip="185.60.219.35",
        src_port=54321,
        dst_port=445,
        protocol="TCP",
        packet_count=5000,
        byte_count=byte_count,
        duration_seconds=duration_seconds,
    )


# ---------------------------------------------------------------------------
# 1. CapacityEstimator unit tests
# ---------------------------------------------------------------------------


class TestCapacityEstimatorEmpty:
    def test_empty_registry_zero_throughput(self):
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.observed_bps == 0.0
        assert result.snapshot.observed_mbps == 0.0

    def test_empty_registry_zero_utilisation(self):
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.utilisation_pct == 0.0

    def test_empty_registry_clear_congestion(self):
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.congestion_state == CongestionState.CLEAR

    def test_empty_registry_zero_flows(self):
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.active_flows == 0
        assert result.snapshot.measurable_flows == 0

    def test_empty_registry_no_jitter(self):
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.mean_jitter_ms is None
        assert result.snapshot.max_jitter_ms is None

    def test_empty_registry_empty_breakdown(self):
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.by_category == []
        assert result.flows == []


class TestCapacityEstimatorSingleFlow:
    def test_single_flow_correct_bps(self, client):
        # 160 000 bytes over 30 s → 160000*8/30 = 42 666.67 bps
        _gaming_flow(client)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        expected_bps = (160_000 * 8) / 30.0
        assert abs(result.snapshot.observed_bps - expected_bps) < 1.0

    def test_single_flow_correct_mbps(self, client):
        _gaming_flow(client)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        expected_mbps = (160_000 * 8) / 30.0 / 1_000_000
        assert abs(result.snapshot.observed_mbps - expected_mbps) < 0.0001

    def test_single_flow_utilisation_on_100mbps_link(self, client):
        _gaming_flow(client)
        est = CapacityEstimator(flow_registry, link_speed_mbps=100.0)
        result = est.estimate()
        # 42 667 bps on 100 Mbps = ~0.04 %
        assert result.snapshot.utilisation_pct < 1.0
        assert result.snapshot.congestion_state == CongestionState.CLEAR

    def test_single_flow_measurable_count(self, client):
        _gaming_flow(client)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.active_flows == 1
        assert result.snapshot.measurable_flows == 1

    def test_single_flow_jitter_reported(self, client):
        _gaming_flow(client)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.mean_jitter_ms == pytest.approx(15.0, abs=0.01)
        assert result.snapshot.max_jitter_ms == pytest.approx(15.0, abs=0.01)

    def test_per_flow_throughput_detail(self, client):
        _gaming_flow(client)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert len(result.flows) == 1
        ft = result.flows[0]
        assert ft.computed_bps is not None
        assert ft.computed_bps > 0
        assert ft.computed_mbps is not None
        assert ft.effective_category == "Gaming"


class TestCapacityEstimatorMultipleFlows:
    def test_multiple_flows_sum_throughput(self, client):
        # gaming: 160000 bytes / 30 s = 42 667 bps
        # bulk:   70000000 bytes / 30 s = 18 666 667 bps
        _gaming_flow(client)
        _bulk_flow(client)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        expected = (160_000 * 8 / 30) + (70_000_000 * 8 / 30)
        assert abs(result.snapshot.observed_bps - expected) < 10.0

    def test_multiple_flows_active_count(self, client):
        _gaming_flow(client)
        _bulk_flow(client)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.active_flows == 2
        assert result.snapshot.measurable_flows == 2

    def test_flow_without_byte_count_not_measurable(self, client):
        _gaming_flow(client)
        # flow with no byte_count
        _submit(client, src_ip="10.0.0.1", dst_ip="10.0.0.2",
                duration_seconds=10.0)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.active_flows == 2
        assert result.snapshot.measurable_flows == 1  # only the gaming flow

    def test_flow_without_duration_not_measurable(self, client):
        _gaming_flow(client)
        _submit(client, src_ip="10.0.0.1", dst_ip="10.0.0.2",
                byte_count=50_000)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.measurable_flows == 1

    def test_per_category_breakdown_sums_to_total(self, client):
        _gaming_flow(client)
        _bulk_flow(client)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        total = sum(cat.observed_bps for cat in result.by_category)
        assert abs(total - result.snapshot.observed_bps) < 1.0

    def test_per_category_share_pct_sums_to_100(self, client):
        _gaming_flow(client)
        _bulk_flow(client)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        total_share = sum(cat.share_pct for cat in result.by_category)
        assert abs(total_share - 100.0) < 0.1

    def test_jitter_mean_across_multiple_flows(self, client):
        # gaming inter_arrival_ms=15, no jitter on bulk → mean = 15
        _gaming_flow(client)
        _bulk_flow(client)
        est = CapacityEstimator(flow_registry)
        result = est.estimate()
        assert result.snapshot.mean_jitter_ms == pytest.approx(15.0, abs=0.01)


class TestCongestionThresholds:
    def test_utilisation_below_60_is_clear(self, client):
        # 1 Mbps on a 100 Mbps link = 1 % → CLEAR
        _submit(client, src_ip="1.1.1.1", dst_ip="2.2.2.2",
                byte_count=1_000_000, duration_seconds=8.0)  # ~1 Mbps
        est = CapacityEstimator(flow_registry, link_speed_mbps=100.0)
        result = est.estimate()
        assert result.snapshot.congestion_state == CongestionState.CLEAR

    def test_utilisation_above_60_is_moderate(self, client):
        # Need > 60 Mbps on a 100 Mbps link
        # 900 000 000 bytes / 12 s = 600 Mbps → cap at 100 Mbps but utilisation > 85 %, use 75 Mbps link
        # 67.5 MB / 8 s = 67.5 Mbps on a 100 Mbps link = 67.5 % → MODERATE
        _submit(client, src_ip="1.1.1.1", dst_ip="2.2.2.2",
                byte_count=67_500_000, duration_seconds=8.0)
        est = CapacityEstimator(flow_registry, link_speed_mbps=100.0)
        result = est.estimate()
        assert result.snapshot.utilisation_pct >= THRESHOLD_MODERATE
        assert result.snapshot.congestion_state == CongestionState.MODERATE

    def test_utilisation_above_85_is_congested(self, client):
        # 90 MB / 8 s = 90 Mbps on 100 Mbps = 90 % → CONGESTED
        _submit(client, src_ip="1.1.1.1", dst_ip="2.2.2.2",
                byte_count=90_000_000, duration_seconds=8.0)
        est = CapacityEstimator(flow_registry, link_speed_mbps=100.0)
        result = est.estimate()
        assert result.snapshot.utilisation_pct > THRESHOLD_CONGESTED
        assert result.snapshot.congestion_state == CongestionState.CONGESTED

    def test_utilisation_capped_at_100_pct(self, client):
        # Submitting more than link speed — must never exceed 100 %
        _submit(client, src_ip="1.1.1.1", dst_ip="2.2.2.2",
                byte_count=10_000_000_000, duration_seconds=1.0)
        est = CapacityEstimator(flow_registry, link_speed_mbps=100.0)
        result = est.estimate()
        assert result.snapshot.utilisation_pct == pytest.approx(100.0, abs=0.01)


class TestLinkSpeedParameter:
    def test_smaller_link_speed_increases_utilisation(self, client):
        _gaming_flow(client)
        est_100 = CapacityEstimator(flow_registry, link_speed_mbps=100.0)
        est_1 = CapacityEstimator(flow_registry, link_speed_mbps=1.0)
        assert est_1.estimate().snapshot.utilisation_pct > est_100.estimate().snapshot.utilisation_pct

    def test_link_speed_returned_in_snapshot(self, client):
        est = CapacityEstimator(flow_registry, link_speed_mbps=50.0)
        result = est.estimate()
        assert result.snapshot.link_speed_mbps == 50.0


# ---------------------------------------------------------------------------
# 2. API integration tests
# ---------------------------------------------------------------------------


class TestCapacityEndpoint:
    def test_empty_registry_returns_zero(self, client):
        resp = client.get("/api/capacity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["snapshot"]["observed_bps"] == 0.0
        assert data["snapshot"]["active_flows"] == 0
        assert data["snapshot"]["congestion_state"] == "clear"

    def test_full_estimate_structure(self, client):
        _gaming_flow(client)
        resp = client.get("/api/capacity")
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshot" in data
        assert "by_category" in data
        assert "flows" in data

    def test_snapshot_fields_present(self, client):
        _gaming_flow(client)
        resp = client.get("/api/capacity")
        snap = resp.json()["snapshot"]
        required = {
            "observed_bps", "observed_mbps", "link_speed_mbps",
            "utilisation_pct", "congestion_state",
            "active_flows", "measurable_flows",
            "estimated_at", "method", "limitation",
        }
        assert required.issubset(snap.keys())

    def test_per_flow_detail_included(self, client):
        _gaming_flow(client)
        resp = client.get("/api/capacity")
        flows = resp.json()["flows"]
        assert len(flows) == 1
        ft = flows[0]
        assert ft["computed_bps"] is not None
        assert ft["effective_category"] == "Gaming"

    def test_link_speed_query_param(self, client):
        _gaming_flow(client)
        resp_100 = client.get("/api/capacity?link_speed_mbps=100")
        resp_1   = client.get("/api/capacity?link_speed_mbps=1")
        util_100 = resp_100.json()["snapshot"]["utilisation_pct"]
        util_1   = resp_1.json()["snapshot"]["utilisation_pct"]
        assert util_1 > util_100

    def test_invalid_link_speed_rejected(self, client):
        resp = client.get("/api/capacity?link_speed_mbps=-1")
        assert resp.status_code == 422

    def test_zero_link_speed_rejected(self, client):
        resp = client.get("/api/capacity?link_speed_mbps=0")
        assert resp.status_code == 422

    def test_capacity_does_not_modify_flow_registry(self, client):
        _gaming_flow(client)
        client.get("/api/capacity")
        assert len(client.get("/api/flows").json()) == 1

    def test_limitation_field_present(self, client):
        resp = client.get("/api/capacity")
        snap = resp.json()["snapshot"]
        assert "limitation" in snap
        assert len(snap["limitation"]) > 10


class TestCapacitySnapshotEndpoint:
    def test_snapshot_only_endpoint(self, client):
        _gaming_flow(client)
        resp = client.get("/api/capacity/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        # snapshot fields present, but no 'flows' or 'by_category'
        assert "observed_bps" in data
        assert "flows" not in data
        assert "by_category" not in data

    def test_snapshot_congestion_state_string(self, client):
        resp = client.get("/api/capacity/snapshot")
        assert resp.status_code == 200
        assert resp.json()["congestion_state"] in ("clear", "moderate", "congested")

    def test_snapshot_link_speed_query_param(self, client):
        _gaming_flow(client)
        resp = client.get("/api/capacity/snapshot?link_speed_mbps=20")
        assert resp.status_code == 200
        assert resp.json()["link_speed_mbps"] == 20.0
