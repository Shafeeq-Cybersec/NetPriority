# NetPriority — Phase 1: Traffic Classifier

Team Mutex · Tata Elxsi TELIPORT Season 4 · Case Study 3

---

## Overview

Phase 1 implements a **metadata-based network traffic classifier** as a FastAPI
service.  It accepts flow metadata (IP addresses, ports, protocol, packet
statistics), applies a configurable rule engine, and returns a traffic category
with a confidence score and a human-readable explanation.

**No packet payloads are inspected at any point.**

---

## Traffic Categories

| Category | DSCP (future) | Typical traffic |
|---|---|---|
| Gaming | 46 | UDP game state updates, Steam, Xbox Live, PSN |
| Video | 34 | RTP video, RTSP streams, WebRTC, adaptive bitrate |
| Signaling | 40 | SIP call setup, STUN/TURN, H.323, MGCP |
| Bulk | — | FTP, SMB, BitTorrent, large TCP downloads |
| Unknown | — | Returned when evidence is insufficient |

---

## Classification Methodology

The classifier uses **multi-rule evidence accumulation**:

1. Every rule in the rule table is evaluated independently against the
   submitted flow metadata.
2. A rule fires when **all** of its conditions are satisfied.
3. Each fired rule adds its weight to its category's score.
4. The category with the highest total score wins, provided it reaches
   the minimum confidence threshold (20 points).
5. If no category reaches the threshold, `Unknown` is returned.

Rules test observable metadata only:

- Destination / source port (exact list or range)
- Transport protocol (TCP / UDP)
- Mean packet size (bytes)
- Inter-packet arrival time (ms)
- Byte rate (bytes/second, derived from byte_count / duration)
- Packet count
- Flow duration

### Why not purely port-based?

A single port match provides weak evidence.  Port 443 carries gaming,
video, signaling, and bulk traffic simultaneously.  The classifier
requires **multiple independent signals** to agree before returning a
high-confidence result.  A flow matched only by one weak port hint
will produce a low score and may fall below the threshold.

### Confidence Score

`confidence_score` is an integer in the range **0–100**.

> ⚠️ This is a **rule-based heuristic score**, not a statistically
> calibrated probability.  It reflects how many independent rule signals
> support the assigned category and how strongly those rules are weighted.

---

## Project Structure (Phase 1 additions)

```
backend/
├── app/
│   ├── models/
│   │   └── flow.py               # Pydantic models: FlowSubmit, FlowRecord,
│   │                             # ClassificationResult, FlowResponse,
│   │                             # ClassificationOverride, TrafficCategory
│   ├── services/
│   │   ├── classifier_rules.py   # Configurable rule table
│   │   ├── classifier_service.py # Stateless rule engine
│   │   └── flow_registry.py      # In-memory flow store
│   └── routers/
│       └── flows.py              # FastAPI router — 4 endpoints
├── tests/
│   └── test_classifier.py        # 43 pytest tests
├── requirements.txt
└── PHASE1_CLASSIFIER.md          # This file
```

---

## API Endpoints

### GET /api/flows
List all observed flows (oldest first).

**Response:** `200 OK` — array of `FlowResponse` objects.

```bash
curl http://localhost:8000/api/flows
```

---

### POST /api/flows
Submit a flow for classification.

**Request body** (all fields except `src_ip` and `dst_ip` are optional):

```json
{
  "src_ip": "192.168.1.50",
  "dst_ip": "203.0.113.10",
  "src_port": 52000,
  "dst_port": 27015,
  "protocol": "UDP",
  "packet_count": 800,
  "byte_count": 160000,
  "duration_seconds": 30.0,
  "inter_arrival_ms": 15.0
}
```

**Response** `201 Created`:

```json
{
  "flow_id": "a1b2c3d4-...",
  "created_at": "2026-10-30T14:00:00Z",
  "src_ip": "192.168.1.50",
  "dst_ip": "203.0.113.10",
  "src_port": 52000,
  "dst_port": 27015,
  "protocol": "UDP",
  "packet_count": 800,
  "byte_count": 160000,
  "duration_seconds": 30.0,
  "mean_packet_size": 200.0,
  "inter_arrival_ms": 15.0,
  "auto_classification": {
    "category": "Gaming",
    "confidence_score": 85,
    "reason": "Flow UDP 192.168.1.50:52000 → 203.0.113.10:27015 classified as Gaming. Matched rules: [gaming_known_ports, gaming_udp_low_latency, gaming_small_udp_packets]. Classification is metadata-based; no payload inspection was performed.",
    "matched_rules": ["gaming_known_ports", "gaming_udp_low_latency", "gaming_small_udp_packets"]
  },
  "manual_category": null,
  "manual_override_reason": null,
  "is_manually_overridden": false,
  "effective_category": "Gaming"
}
```

---

### GET /api/flows/{flow_id}
Retrieve one flow by its UUID.

```bash
curl http://localhost:8000/api/flows/a1b2c3d4-...
```

**Response:** `200 OK` — single `FlowResponse` object.  
**Error:** `404 Not Found` if the ID does not exist.

---

### PATCH /api/flows/{flow_id}/classification
Manually override a classification.

```bash
curl -X PATCH http://localhost:8000/api/flows/a1b2c3d4-.../classification \
  -H "Content-Type: application/json" \
  -d '{"category": "Bulk", "reason": "Operator confirmed this is a backup job."}'
```

**Request body:**

```json
{
  "category": "Bulk",
  "reason": "Optional explanation (max 500 chars)"
}
```

**Response:** `200 OK` — updated `FlowResponse` with:
- `is_manually_overridden: true`
- `manual_category`: the corrected category
- `effective_category`: reflects the override
- `auto_classification`: **unchanged** — original result is always preserved

**Constraints:**
- `category` must be `Gaming`, `Video`, `Signaling`, or `Bulk`.
- `Unknown` is not a valid manual category (returns `422`).

---

## Installation

### Prerequisites
- Python 3.10+
- The existing `backend/venv` created in Phase 0

### Install dependencies

```powershell
cd backend
.\venv\Scripts\activate
pip install -r requirements.txt
```

---

## Running the Server

```powershell
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive API docs: http://localhost:8000/docs

---

## Running the Tests

```powershell
cd backend
.\venv\Scripts\activate
python -m pytest tests/test_classifier.py -v
```

Expected: **43 passed**.

---

## Example: Unknown Classification

A flow with only IP addresses and no statistics:

```json
{
  "src_ip": "192.168.1.1",
  "dst_ip": "10.0.0.1",
  "protocol": "TCP"
}
```

Response:

```json
{
  "auto_classification": {
    "category": "Unknown",
    "confidence_score": 0,
    "reason": "No classification rules matched this flow.",
    "matched_rules": []
  },
  "effective_category": "Unknown"
}
```

---

## Current Limitations

| Limitation | Notes |
|---|---|
| In-memory storage only | All flows are lost on server restart. Phase 3+ will add persistence. |
| No live packet capture | This phase accepts submitted metadata only. Phase 2 adds live link monitoring. |
| Rule weights are hand-tuned | No training data or statistical calibration. Weights should be validated against real traffic traces. |
| Port-based rules are heuristic | Port 443 is used by many categories; rules requiring additional metadata signals reduce false positives but do not eliminate them. |
| No IPv6 validation | IP addresses are accepted as strings; format validation is basic. |
| No authentication | The correction endpoint has no access control. Phase 3 adds admin auth. |
| Windows only (dev) | The server runs on Windows for development but is designed for Linux deployment. |
