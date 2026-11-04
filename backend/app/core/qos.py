"""
qos.py — QoS marking policy: traffic category → DSCP / queue treatment.

The classifier answers "what kind of traffic is this?".  This module is the
bridge to traffic control: it answers "how should that traffic be marked?".

Each category maps to a standard DiffServ code point (DSCP), a priority
tier, an output queue label and a short treatment description.  Markings
follow common DiffServ conventions:

    EF   (46)  Expedited Forwarding   — low loss, low latency, low jitter
    CS5  (40)  Class Selector 5       — priority / control traffic
    AF41 (34)  Assured Forwarding 4/1 — guaranteed bandwidth, some jitter
    CS0  (0)   Default / Best Effort  — no special treatment

No packet is actually marked by this phase — the values are policy
*recommendations* returned with each classification, ready for a future
enforcement layer (tc / HTB on Linux) to apply.

The table is plain data so operators can tune it without touching logic.
"""

from typing import Any

# ---------------------------------------------------------------------------
# POLICY TABLE — ordered from highest to lowest priority
# ---------------------------------------------------------------------------

QOS_POLICIES: dict[str, dict[str, Any]] = {
    "Gaming": {
        "category": "Gaming",
        "dscp": 46,
        "dscp_class": "EF",
        "priority": "Critical",
        "queue": "Q1",
        "treatment": (
            "Expedited forwarding — smallest queue, lowest latency and jitter. "
            "Game state updates are small but time-critical."
        ),
    },
    "Signaling": {
        "category": "Signaling",
        "dscp": 40,
        "dscp_class": "CS5",
        "priority": "High",
        "queue": "Q2",
        "treatment": (
            "Priority forwarding — call setup and control traffic is low volume "
            "but delays it cause user-visible failures."
        ),
    },
    "Video": {
        "category": "Video",
        "dscp": 34,
        "dscp_class": "AF41",
        "priority": "Elevated",
        "queue": "Q3",
        "treatment": (
            "Assured bandwidth — sustained throughput with moderate jitter "
            "tolerance for adaptive-bitrate streams."
        ),
    },
    "Bulk": {
        "category": "Bulk",
        "dscp": 0,
        "dscp_class": "CS0",
        "priority": "Best effort",
        "queue": "Q4",
        "treatment": (
            "Best effort — large transfers yield to all real-time traffic "
            "and fill only the leftover capacity."
        ),
    },
    "Unknown": {
        "category": "Unknown",
        "dscp": 0,
        "dscp_class": "CS0",
        "priority": "Unclassified",
        "queue": "Q4",
        "treatment": (
            "Default forwarding — no special treatment until the flow has "
            "enough metadata to be classified."
        ),
    },
}

# Category used when a caller asks for a category that has no policy entry.
DEFAULT_POLICY_CATEGORY = "Unknown"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def policy_for(category: str) -> dict[str, Any]:
    """
    Return a copy of the QoS policy for the given category name.

    Unknown category names fall back to the default (best-effort) policy
    rather than raising, so a new classifier category can never break the
    response pipeline.
    """
    return dict(
        QOS_POLICIES.get(category, QOS_POLICIES[DEFAULT_POLICY_CATEGORY])
    )


def all_policies() -> list[dict[str, Any]]:
    """Return every policy, ordered highest priority first."""
    return [dict(policy) for policy in QOS_POLICIES.values()]
