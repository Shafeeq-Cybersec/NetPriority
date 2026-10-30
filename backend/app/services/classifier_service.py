"""
classifier_service.py — metadata-based traffic classifier.

Architecture
------------
The classifier applies a configurable rule table to flow metadata and
produces a ClassificationResult.  No packet payloads are ever read.

Classification algorithm (multi-rule evidence accumulation)
------------------------------------------------------------
1.  For each rule in the rule table, evaluate whether every condition
    in that rule's "conditions" dict is satisfied by the submitted
    flow metadata.

2.  When ALL conditions of a rule are satisfied, add the rule's weight
    to that rule's category score and record the rule name.

3.  After evaluating all rules, sum the scores per category.

4.  The category with the highest total score wins, provided that total
    is at least MIN_CONFIDENCE_THRESHOLD.

5.  The winning confidence_score is the winning category's total score,
    clamped to 100.

6.  If no category reaches MIN_CONFIDENCE_THRESHOLD, the result is
    UNKNOWN with confidence 0.

This approach deliberately avoids classifying traffic purely from a
single port match — multiple independent signals must agree before a
high-confidence result is returned.

Confidence disclaimer
---------------------
The confidence_score is a *rule-based heuristic score* (0–100).
It is NOT a statistically calibrated probability estimate.
It reflects how many independent rule signals support the assigned
category and how strongly those rules are weighted.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from app.models.flow import (
    ClassificationResult,
    FlowSubmit,
    Protocol,
    TrafficCategory,
)
from app.services.classifier_rules import DEFAULT_RULES

# Minimum total score a category must accumulate before it is returned
# as a real classification.  Below this threshold the result is UNKNOWN.
MIN_CONFIDENCE_THRESHOLD = 20

# Hard cap — confidence_score never exceeds this.
MAX_CONFIDENCE = 100


class ClassifierService:
    """
    Stateless traffic classifier.

    Accepts a FlowSubmit and returns a ClassificationResult.
    A custom rule table can be injected for testing or operator overrides.
    """

    def __init__(self, rules: Optional[list[dict]] = None) -> None:
        self._rules: list[dict] = rules if rules is not None else DEFAULT_RULES

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, flow: FlowSubmit) -> ClassificationResult:
        """
        Classify a flow and return a ClassificationResult.

        Parameters
        ----------
        flow:
            The submitted flow metadata.

        Returns
        -------
        ClassificationResult
            category, confidence_score, reason, matched_rules.
        """
        # Accumulate evidence per category.
        scores: dict[TrafficCategory, int] = defaultdict(int)
        matched: dict[TrafficCategory, list[str]] = defaultdict(list)

        # Compute derived metrics once.
        byte_rate = self._byte_rate(flow)

        for rule in self._rules:
            if self._evaluate_rule(rule, flow, byte_rate):
                cat = rule["category"]
                scores[cat] += rule["weight"]
                matched[cat].append(rule["name"])

        # Pick winner.
        if not scores:
            return self._unknown_result("No classification rules matched this flow.")

        best_cat = max(scores, key=lambda c: scores[c])
        best_score = min(scores[best_cat], MAX_CONFIDENCE)

        if best_score < MIN_CONFIDENCE_THRESHOLD:
            return self._unknown_result(
                f"Highest score was {best_score} (threshold {MIN_CONFIDENCE_THRESHOLD}). "
                "Insufficient metadata to classify confidently."
            )

        reason = self._build_reason(best_cat, matched[best_cat], flow)

        return ClassificationResult(
            category=best_cat,
            confidence_score=best_score,
            reason=reason,
            matched_rules=matched[best_cat],
        )

    # ------------------------------------------------------------------
    # Rule evaluation
    # ------------------------------------------------------------------

    def _evaluate_rule(
        self,
        rule: dict,
        flow: FlowSubmit,
        byte_rate: Optional[float],
    ) -> bool:
        """
        Return True only if ALL conditions in the rule are satisfied.

        Missing metadata (None values) cause condition checks to be
        skipped — they do not cause the rule to fail.  This means a
        rule can still partially fire on incomplete data, but only the
        conditions that CAN be evaluated are checked.

        Protocol-restricting conditions (udp_only / tcp_only) are
        hard failures: if the flow's protocol disagrees, the rule
        is rejected.
        """
        cond = rule.get("conditions", {})

        # --- protocol filters (hard) ---
        if cond.get("udp_only") and flow.protocol != Protocol.UDP:
            return False
        if cond.get("tcp_only") and flow.protocol != Protocol.TCP:
            return False

        # --- destination port exact list ---
        if "dst_ports" in cond and flow.dst_port is not None:
            if flow.dst_port not in cond["dst_ports"]:
                return False
        elif "dst_ports" in cond and flow.dst_port is None:
            # Can't verify — skip this condition but don't fail the rule
            # only if there are other conditions that still match.
            # We handle this by checking if dst_ports is the ONLY condition.
            if len(cond) == 1:
                return False

        # --- source port exact list ---
        if "src_ports" in cond and flow.src_port is not None:
            if flow.src_port not in cond["src_ports"]:
                return False
        elif "src_ports" in cond and flow.src_port is None:
            if len(cond) == 1:
                return False

        # --- destination port ranges ---
        if "dst_port_ranges" in cond:
            if flow.dst_port is None:
                if len(cond) <= 2:  # only range + possibly protocol filter
                    return False
            else:
                matched_range = any(
                    lo <= flow.dst_port <= hi
                    for lo, hi in cond["dst_port_ranges"]
                )
                if not matched_range:
                    return False

        # --- source port ranges ---
        if "src_port_ranges" in cond:
            if flow.src_port is None:
                if len(cond) <= 2:
                    return False
            else:
                matched_range = any(
                    lo <= flow.src_port <= hi
                    for lo, hi in cond["src_port_ranges"]
                )
                if not matched_range:
                    return False

        # --- mean packet size ---
        if "max_mean_pkt_size" in cond and flow.mean_packet_size is not None:
            if flow.mean_packet_size > cond["max_mean_pkt_size"]:
                return False
        if "min_mean_pkt_size" in cond and flow.mean_packet_size is not None:
            if flow.mean_packet_size < cond["min_mean_pkt_size"]:
                return False
        if "max_mean_pkt_size" in cond and flow.mean_packet_size is None:
            # Required numeric condition, data absent — skip rule
            return False
        if "min_mean_pkt_size" in cond and flow.mean_packet_size is None:
            return False

        # --- inter-arrival time ---
        if "max_inter_arrival" in cond and flow.inter_arrival_ms is not None:
            if flow.inter_arrival_ms > cond["max_inter_arrival"]:
                return False
        if "min_inter_arrival" in cond and flow.inter_arrival_ms is not None:
            if flow.inter_arrival_ms < cond["min_inter_arrival"]:
                return False
        if "max_inter_arrival" in cond and flow.inter_arrival_ms is None:
            return False
        if "min_inter_arrival" in cond and flow.inter_arrival_ms is None:
            return False

        # --- byte rate ---
        if "min_byte_rate" in cond:
            if byte_rate is None:
                return False
            if byte_rate < cond["min_byte_rate"]:
                return False
        if "max_byte_rate" in cond:
            if byte_rate is None:
                return False
            if byte_rate > cond["max_byte_rate"]:
                return False

        # --- packet count ---
        if "min_packet_count" in cond and flow.packet_count is not None:
            if flow.packet_count < cond["min_packet_count"]:
                return False
        if "min_packet_count" in cond and flow.packet_count is None:
            return False

        # --- duration ---
        if "min_duration" in cond and flow.duration_seconds is not None:
            if flow.duration_seconds < cond["min_duration"]:
                return False
        if "min_duration" in cond and flow.duration_seconds is None:
            return False

        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _byte_rate(flow: FlowSubmit) -> Optional[float]:
        """Compute bytes-per-second from flow counters, or None if unavailable."""
        if (
            flow.byte_count is not None
            and flow.duration_seconds is not None
            and flow.duration_seconds > 0
        ):
            return flow.byte_count / flow.duration_seconds
        return None

    @staticmethod
    def _unknown_result(reason: str) -> ClassificationResult:
        return ClassificationResult(
            category=TrafficCategory.UNKNOWN,
            confidence_score=0,
            reason=reason,
            matched_rules=[],
        )

    @staticmethod
    def _build_reason(
        category: TrafficCategory,
        matched_rule_names: list[str],
        flow: FlowSubmit,
    ) -> str:
        """Build a human-readable explanation string."""
        proto = flow.protocol.value
        src = f"{flow.src_ip}:{flow.src_port}" if flow.src_port else flow.src_ip
        dst = f"{flow.dst_ip}:{flow.dst_port}" if flow.dst_port else flow.dst_ip
        rules_text = ", ".join(matched_rule_names)
        return (
            f"Flow {proto} {src} → {dst} classified as {category.value}. "
            f"Matched rules: [{rules_text}]. "
            f"Classification is metadata-based; no payload inspection was performed."
        )
