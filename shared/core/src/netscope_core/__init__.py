"""NetScope shared diagnostic engine.

One package, standard library only: probes (DNS, TCP, TLS, HTTP,
route, speed), latency statistics, error classification, the verdict
engine, troubleshooting rules, and report renderers. All results
follow the shared schemas in ``shared/schemas/``.
"""

from .models import VERSION as __version__
from .models import (
    CertificateInfo,
    HostReport,
    Measurement,
    PacketStats,
    ProbeError,
    ProbeResult,
    Target,
)
from .stats import LatencyStats, latency_stats, packet_loss

__all__ = [
    "__version__",
    "CertificateInfo",
    "HostReport",
    "LatencyStats",
    "Measurement",
    "PacketStats",
    "ProbeError",
    "ProbeResult",
    "Target",
    "latency_stats",
    "packet_loss",
]
