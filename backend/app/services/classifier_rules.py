"""
classifier_rules.py — configurable rule definitions for the traffic classifier.

Design intent
-------------
Each rule is a pure-Python dict so that operators can override defaults
by supplying a custom rules file or environment variable without touching
source code.  The classifier_service consumes this module; the rules are
never hardwired into business logic.

Rule schema
-----------
{
    "name":        str   — unique identifier shown in matched_rules
    "category":    TrafficCategory value
    "weight":      int   — contribution to confidence when this rule fires
                          (all fired weights are summed and clamped to 100)
    "description": str   — human-readable purpose of the rule
    "conditions":  dict  — checked by ClassifierService._evaluate_rule()
}

Condition keys (all optional — omit to ignore that dimension):
    udp_only          bool  — True → only fires on UDP
    tcp_only          bool  — True → only fires on TCP
    dst_ports         list[int]  — destination port must be in list
    src_ports         list[int]  — source port must be in list
    dst_port_ranges   list[[lo, hi]]  — destination port in any range
    src_port_ranges   list[[lo, hi]]  — source port in any range
    max_mean_pkt_size float  — mean_packet_size must be ≤ value (bytes)
    min_mean_pkt_size float  — mean_packet_size must be ≥ value (bytes)
    max_inter_arrival float  — inter_arrival_ms must be ≤ value (ms)
    min_inter_arrival float  — inter_arrival_ms must be ≥ value (ms)
    min_byte_rate     float  — byte_count/duration_seconds must be ≥ value
    max_byte_rate     float  — byte_count/duration_seconds must be ≤ value
    min_packet_count  int    — packet_count must be ≥ value
    min_duration      float  — duration_seconds must be ≥ value (s)

Important: a rule only CONTRIBUTES evidence for its category; it does not
exclusively assign it.  The classifier tallies evidence across all rules
for all categories and picks the highest-scoring category.
"""

from app.models.flow import TrafficCategory

# ---------------------------------------------------------------------------
# DEFAULT RULE TABLE
# ---------------------------------------------------------------------------
# Rules are ordered loosely by specificity (most specific first) but order
# does not affect correctness — all rules are evaluated independently.

DEFAULT_RULES: list[dict] = [

    # ===================================================================
    # GAMING rules
    # Gaming traffic characteristics:
    #   - Predominantly UDP (low-latency, loss-tolerant)
    #   - Small packet sizes (state updates, not bulk media)
    #   - Very low inter-arrival times (high send frequency)
    #   - Well-known gaming ports for popular engines/platforms
    # ===================================================================

    {
        "name": "gaming_udp_low_latency",
        "category": TrafficCategory.GAMING,
        "weight": 35,
        "description": (
            "UDP flow with very low inter-arrival time (<= 20 ms), "
            "characteristic of real-time game state updates."
        ),
        "conditions": {
            "udp_only": True,
            "max_inter_arrival": 20.0,
            "max_mean_pkt_size": 512.0,
        },
    },
    {
        "name": "gaming_known_ports",
        "category": TrafficCategory.GAMING,
        "weight": 30,
        "description": (
            "Destination port matches well-known gaming service ports "
            "(Steam, Xbox Live, PSN, Valve, EA Origin, Epic)."
        ),
        "conditions": {
            # Steam: 27015-27050 (game/voice), Xbox Live: 3074,
            # PSN: 3478-3480, 3659, Epic: 5222
            "dst_ports": [3074, 3478, 3479, 3480, 3659, 5222],
            "dst_port_ranges": [[27015, 27050]],
        },
    },
    {
        "name": "gaming_small_udp_packets",
        "category": TrafficCategory.GAMING,
        "weight": 20,
        "description": (
            "UDP flow with small mean packet size (<= 300 bytes), "
            "consistent with game state/telemetry messages."
        ),
        "conditions": {
            "udp_only": True,
            "max_mean_pkt_size": 300.0,
        },
    },

    # ===================================================================
    # VIDEO rules
    # Video streaming / conferencing characteristics:
    #   - Large mean packet sizes (close to MTU for media payloads)
    #   - Moderate-to-high byte rate (sustained throughput)
    #   - Well-known streaming ports: RTSP 554, RTP 5004/5005,
    #     RTMP 1935, HLS/DASH over HTTPS (443), SRT 9000
    #   - Video conferencing: WebRTC UDP typically 1024-65535 but
    #     we rely on RTP characteristic packet sizes + rate
    # ===================================================================

    {
        "name": "video_streaming_ports",
        "category": TrafficCategory.VIDEO,
        "weight": 35,
        "description": (
            "Destination port matches well-known video streaming protocols: "
            "RTSP (554), RTP (5004/5005), RTMP (1935), SRT (9000)."
        ),
        "conditions": {
            "dst_ports": [554, 5004, 5005, 1935, 9000],
        },
    },
    {
        "name": "video_large_udp_packets",
        "category": TrafficCategory.VIDEO,
        "weight": 30,
        "description": (
            "UDP flow with large mean packet size (>= 900 bytes) and "
            "sustained byte rate >= 500 KB/s, consistent with RTP video."
        ),
        "conditions": {
            "udp_only": True,
            "min_mean_pkt_size": 900.0,
            "min_byte_rate": 500_000.0,
        },
    },
    {
        "name": "video_high_throughput_tcp",
        "category": TrafficCategory.VIDEO,
        "weight": 25,
        "description": (
            "Long-lived TCP flow with high byte rate (>= 1 MB/s) and "
            "large mean packet size (>= 800 bytes), consistent with "
            "adaptive bitrate video over HTTPS."
        ),
        "conditions": {
            "tcp_only": True,
            "min_byte_rate": 1_000_000.0,
            "min_mean_pkt_size": 800.0,
            "min_duration": 5.0,
        },
    },
    {
        "name": "video_webrtc_range",
        "category": TrafficCategory.VIDEO,
        "weight": 20,
        "description": (
            "UDP flow in the ephemeral range 49152–65535 with low inter-arrival "
            "(<= 50 ms) and large packets (>= 700 bytes), "
            "consistent with WebRTC video/audio."
        ),
        "conditions": {
            "udp_only": True,
            "dst_port_ranges": [[49152, 65535]],
            "min_mean_pkt_size": 700.0,
            "max_inter_arrival": 50.0,
        },
    },

    # ===================================================================
    # SIGNALING rules
    # Signaling / VoIP / call-setup characteristics:
    #   - Very small packets (SIP/SDP messages, RTCP control)
    #   - Low byte rate (control plane, not media plane)
    #   - Well-known ports: SIP 5060/5061, STUN 3478/3479,
    #     RTCP 5005, MGCP 2427/2727, H.323 1720
    # ===================================================================

    {
        "name": "signaling_sip_ports",
        "category": TrafficCategory.SIGNALING,
        "weight": 45,
        "description": (
            "Port matches SIP (5060/5061), STUN (3478/3479), "
            "MGCP (2427/2727), or H.323 (1720) — standard VoIP signaling."
        ),
        "conditions": {
            "dst_ports": [5060, 5061, 3478, 3479, 2427, 2727, 1720],
        },
    },
    {
        "name": "signaling_small_low_rate",
        "category": TrafficCategory.SIGNALING,
        "weight": 30,
        "description": (
            "Flow with very small mean packet size (<= 200 bytes) and "
            "low byte rate (<= 50 KB/s), consistent with control/signaling."
        ),
        "conditions": {
            "max_mean_pkt_size": 200.0,
            "max_byte_rate": 50_000.0,
        },
    },
    {
        "name": "signaling_stun_udp",
        "category": TrafficCategory.SIGNALING,
        "weight": 35,
        "description": (
            "UDP flow to port 3478 or 3479 with very small packets "
            "(<= 100 bytes), classic STUN/TURN binding requests."
        ),
        "conditions": {
            "udp_only": True,
            "dst_ports": [3478, 3479],
            "max_mean_pkt_size": 100.0,
        },
    },

    # ===================================================================
    # BULK rules
    # Bulk transfer characteristics:
    #   - Very large mean packet sizes (near MTU, 1400–1500 bytes)
    #   - Very high byte rate (maximising throughput)
    #   - Long-lived flows
    #   - Well-known ports: FTP 20/21, SMB 445, NFS 2049,
    #     BitTorrent 6881-6889, QUIC 443 UDP high rate
    # ===================================================================

    {
        "name": "bulk_high_rate_tcp",
        "category": TrafficCategory.BULK,
        "weight": 35,
        "description": (
            "Long-lived TCP flow (>= 10 s) with very high byte rate "
            "(>= 2 MB/s) and near-MTU packet size (>= 1200 bytes)."
        ),
        "conditions": {
            "tcp_only": True,
            "min_byte_rate": 2_000_000.0,
            "min_mean_pkt_size": 1200.0,
            "min_duration": 10.0,
        },
    },
    {
        "name": "bulk_file_transfer_ports",
        "category": TrafficCategory.BULK,
        "weight": 40,
        "description": (
            "Destination port matches file-transfer protocols: "
            "FTP-data (20), FTP (21), SMB (445), NFS (2049)."
        ),
        "conditions": {
            "dst_ports": [20, 21, 445, 2049],
        },
    },
    {
        "name": "bulk_bittorrent_ports",
        "category": TrafficCategory.BULK,
        "weight": 30,
        "description": (
            "Destination port in the BitTorrent default range (6881–6889)."
        ),
        "conditions": {
            "dst_port_ranges": [[6881, 6889]],
        },
    },
    {
        "name": "bulk_large_long_flow",
        "category": TrafficCategory.BULK,
        "weight": 25,
        "description": (
            "Flow with large mean packet size (>= 1100 bytes), "
            "many packets (>= 1000), and long duration (>= 30 s), "
            "consistent with a sustained download or backup."
        ),
        "conditions": {
            "min_mean_pkt_size": 1100.0,
            "min_packet_count": 1000,
            "min_duration": 30.0,
        },
    },
]
