# NetPriority — QoS Marking Policy

The classifier answers **what kind of traffic is this?**.
The QoS policy layer answers **how should that traffic be marked?**.

Every flow response now carries a `qos` object with a recommended DiffServ
code point (DSCP), priority tier, output queue and treatment description,
derived from the flow's **effective** category (manual override included).

> Marking is a **recommendation only** in this phase. No packet is marked and
> no traffic is shaped yet — these values are the contract a future Linux
> `tc` / HTB enforcement layer will consume.

---

## Policy table

| Category | DSCP | Class | Priority | Queue | Treatment |
|---|---|---|---|---|---|
| Gaming | 46 | EF | Critical | Q1 | Smallest queue, lowest latency and jitter |
| Signaling | 40 | CS5 | High | Q2 | Priority forwarding for control traffic |
| Video | 34 | AF41 | Elevated | Q3 | Assured bandwidth, moderate jitter tolerance |
| Bulk | 0 | CS0 | Best effort | Q4 | Yields to all real-time traffic |
| Unknown | 0 | CS0 | Unclassified | Q4 | Default until a category is confirmed |

Ordering runs from highest to lowest priority. DSCP values are standard
DiffServ code points (0–63), defined in `app/core/qos.py` as plain data so
operators can tune the table without touching business logic.

---

## API

### GET /api/qos/policies

Returns the full policy table, highest priority first.

```json
[
  {
    "category": "Gaming",
    "dscp": 46,
    "dscp_class": "EF",
    "priority": "Critical",
    "queue": "Q1",
    "treatment": "Expedited forwarding — smallest queue, lowest latency and jitter. Game state updates are small but time-critical."
  }
]
```

### `qos` on every flow response

`GET /api/flows`, `POST /api/flows`, `GET /api/flows/{flow_id}` and
`PATCH /api/flows/{flow_id}/classification` all include the recommendation:

```json
{
  "effective_category": "Gaming",
  "auto_classification": { "category": "Gaming", "confidence_score": 85 },
  "qos": {
    "category": "Gaming",
    "dscp": 46,
    "dscp_class": "EF",
    "priority": "Critical",
    "queue": "Q1",
    "treatment": "Expedited forwarding — smallest queue, lowest latency and jitter. ..."
  }
}
```

A manual classification override changes `qos` to match the corrected
category while `auto_classification` is preserved unchanged, so a correction
immediately corrects the recommended marking too.

---

## Frontend

- The classification card shows the recommended marking
  (`DSCP 46 · EF`, queue, priority) with the treatment as a tooltip.
- A **QoS Marking Policy** panel below the classifier lists the whole table and
  highlights the row for the currently displayed flow.

---

## Tests

```powershell
cd backend
.\venv\Scripts\activate
python -m pytest tests/test_qos_policy.py -v
```

Expected: **19 passed** (81 total with the classifier suite).
