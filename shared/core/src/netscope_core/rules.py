"""Rule-based troubleshooting.

The engine reads a finished :class:`~netscope_core.models.HostReport`
and emits findings. Every finding keeps three things separate:

- ``fact`` — what was measured, with the numbers. Facts never contain
  a cause.
- ``possible_causes`` — hypotheses that would explain the fact. They
  are labelled as possibilities, never merged into the fact.
- ``recommendations`` — verification steps the user can take. They
  are advice; nothing here changes a system setting or runs a command.

Confidence follows the strength of the underlying measurement. A
captive portal, in particular, can only ever be reported as a
suspicion: the observable evidence (a redirect to a different host on
plain HTTP) has innocent explanations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import HostReport


@dataclass
class Finding:
    topic: str
    fact: str
    possible_causes: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    confidence: str = "low"  # high | medium | low


def analyze(report: "HostReport") -> list[Finding]:
    """Derive troubleshooting findings from a completed host report."""
    findings: list[Finding] = []
    findings.extend(_dns_findings(report))
    findings.extend(_tcp_findings(report))
    findings.extend(_tls_findings(report))
    findings.extend(_http_findings(report))
    return findings


def _dns_findings(report: "HostReport") -> list[Finding]:
    dns = report.dns
    out: list[Finding] = []

    if dns.suspect_poisoning:
        public_addresses = sorted(
            {addr for r in dns.resolvers if r.status == "ok" for addr in r.addresses}
        )
        out.append(Finding(
            topic="dns-poisoning",
            fact=(
                f"The system resolver returned {', '.join(dns.system_addresses)} for "
                f"{dns.hostname}; public resolvers returned "
                f"{', '.join(public_addresses) or 'no addresses'}. The two sets share "
                "no address."
            ),
            possible_causes=[
                "The network's resolver is intercepting or rewriting DNS answers.",
                "The router's DNS settings have been changed or compromised.",
                "A captive or filtered network is substituting its own answers.",
            ],
            recommendations=[
                "Repeat the check on a different network (for example a phone hotspot) and compare the addresses.",
                "Check which DNS servers the router and this device are configured to use.",
                "Compare with an encrypted DNS lookup (DoH) for the same name.",
            ],
            confidence="high",
        ))

    system_ok = bool(dns.system_addresses)
    public_ok = any(r.status == "ok" and r.addresses for r in dns.resolvers)
    if not system_ok and public_ok:
        out.append(Finding(
            topic="dns-blocked",
            fact=(
                f"The system resolver returned no addresses for {dns.hostname} "
                f"({dns.system_error or 'empty answer'}), while at least one public "
                "resolver answered with addresses."
            ),
            possible_causes=[
                "The configured resolver is filtering this name.",
                "The configured resolver is misconfigured or unreachable for this query.",
                "Local DNS software (security tools, router filters) is intercepting the query.",
            ],
            recommendations=[
                "Note which resolver the system is configured to use and test it directly.",
                "Try the same lookup from another device on the same network.",
            ],
            confidence="high",
        ))
    elif not system_ok and dns.resolvers and all(r.status == "nxdomain" for r in dns.resolvers):
        out.append(Finding(
            topic="dns-nxdomain",
            fact=f"Every resolver answered NXDOMAIN for {dns.hostname}: the name is reported as not existing.",
            possible_causes=[
                "The domain name really does not exist (check the spelling).",
                "Resolvers are forging NXDOMAIN answers for a name that exists.",
            ],
            recommendations=[
                "Verify the exact spelling of the name.",
                "Look the name up from a different network and compare.",
            ],
            confidence="medium",
        ))
    elif not system_ok and dns.resolvers and all(r.status in ("timeout", "error") for r in dns.resolvers):
        out.append(Finding(
            topic="dns-unreachable",
            fact=(
                f"No resolver answered for {dns.hostname}: the system resolver failed "
                "and every public resolver query timed out or errored."
            ),
            possible_causes=[
                "The network path to DNS servers is broken or blocked (UDP/53 filtered).",
                "The device has no working internet connection at all.",
            ],
            recommendations=[
                "Check whether any other name resolves on this device.",
                "Check the device's basic connectivity (gateway, link state).",
            ],
            confidence="medium",
        ))

    if dns.partial_nxdomain:
        out.append(Finding(
            topic="dns-inconsistent",
            fact=(
                f"Resolvers disagree about {dns.hostname}: at least one answered "
                "NXDOMAIN while at least one returned addresses."
            ),
            possible_causes=[
                "One resolver (or the path to it) is forging NXDOMAIN answers.",
                "The resolvers hold different cached data during a DNS change.",
            ],
            recommendations=[
                "Repeat the check after a few minutes to rule out a DNS change in progress.",
                "Identify which resolver returns NXDOMAIN and test it with a known-good name.",
            ],
            confidence="medium",
        ))
    return out


def _tcp_findings(report: "HostReport") -> list[Finding]:
    out: list[Finding] = []
    for port in (443, 80):
        result = report.tcp.get(port)
        if result is None or not result.attempts:
            continue
        stats = result.latency
        if result.successes > 0 and result.loss_pct >= 25.0:
            out.append(Finding(
                topic="instability",
                fact=(
                    f"{result.successes} of {len(result.attempts)} TCP connections to "
                    f"port {port} succeeded ({result.loss_pct:.0f}% loss)."
                ),
                possible_causes=[
                    "An unstable link (weak Wi-Fi signal, failing cable, overloaded router).",
                    "Congestion or rate limiting on the path.",
                    "The destination shedding load.",
                ],
                recommendations=[
                    "Repeat the test; intermittent loss that persists is a link problem, not a fluke.",
                    "Compare on a wired connection or a different network if available.",
                ],
                confidence="medium",
            ))
        if stats.avg is not None and stats.avg > 400.0:
            out.append(Finding(
                topic="high-latency",
                fact=(
                    f"TCP connections to port {port} took {stats.avg:.0f} ms on average "
                    f"(median {stats.median:.0f} ms, p95 {stats.p95:.0f} ms over "
                    f"{stats.count} connections)."
                ),
                possible_causes=[
                    "Network congestion between this device and the destination.",
                    "Wireless interference or a weak signal adding retransmissions.",
                    "A distant or overloaded destination.",
                    "Router load (other traffic, weak hardware).",
                ],
                recommendations=[
                    "Compare with a nearer, known-fast host to separate local from path latency.",
                    "Repeat at a different time of day to check for congestion patterns.",
                ],
                confidence="medium",
            ))
        if result.successes == 0 and result.dominant_error == "refused":
            out.append(Finding(
                topic="connection-refused",
                fact=f"Every connection to port {port} was actively refused.",
                possible_causes=[
                    "No service is listening on that port (the service is down).",
                    "A firewall at the destination is configured to reject connections.",
                ],
                recommendations=[
                    "If you operate the service, check that it is running and listening on this port.",
                ],
                confidence="medium",
            ))
    return out


def _tls_findings(report: "HostReport") -> list[Finding]:
    tls = report.tls
    out: list[Finding] = []
    if tls is None or tls.ok:
        return out
    tcp443 = report.tcp.get(443)
    if (
        tls.failed_phase == "handshake"
        and tcp443 is not None
        and tcp443.successes > 0
        and tls.error_kind in ("reset", "timeout")
    ):
        detail = (
            "was reset" if tls.error_kind == "reset" else "never completed"
        )
        out.append(Finding(
            topic="tls-blocking",
            fact=(
                f"TCP connections to port 443 open normally, but the TLS handshake "
                f"{detail} once the site name (SNI) was sent in the ClientHello."
            ),
            possible_causes=[
                "Name-based (SNI) filtering on the network path is interrupting the handshake.",
                "A middlebox or security appliance is resetting connections it cannot inspect.",
            ],
            recommendations=[
                "Repeat the check from a different network; if the handshake completes there, the block is on this path.",
                "Compare with a host whose name is unlikely to be filtered, to confirm the failure follows the name.",
            ],
            confidence="high" if tls.error_kind == "reset" else "medium",
        ))
    if tls.error_kind == "certificate":
        out.append(Finding(
            topic="tls-certificate",
            fact=f"Certificate validation failed during the TLS handshake: {tls.error}.",
            possible_causes=[
                "The server's certificate is expired or misconfigured.",
                "The connection is being intercepted by a proxy presenting its own certificate.",
            ],
            recommendations=[
                "Check the device's date and time; a wrong clock fails validation.",
                "Compare the certificate from a different network.",
            ],
            confidence="medium",
        ))
    return out


def _http_findings(report: "HostReport") -> list[Finding]:
    out: list[Finding] = []
    https = report.http.get("https")
    plain = report.http.get("http")

    for scheme, result in (("https", https), ("http", plain)):
        if result is not None and result.ok and result.markers:
            out.append(Finding(
                topic="http-filtered",
                fact=(
                    f"The {scheme.upper()} response for {report.host} is a block page: "
                    f"it contains the filtering markers {', '.join(result.markers)}."
                ),
                possible_causes=[
                    "An ISP or network filtering service is substituting its own page for the site.",
                    "A local security product is blocking the page.",
                ],
                recommendations=[
                    "Repeat the check from a different network to identify which network serves the block page.",
                ],
                confidence="high" if scheme == "https" else "medium",
            ))

    if plain is not None and plain.ok and plain.final_host and plain.final_host != report.host:
        out.append(Finding(
            topic="captive-portal-suspected",
            fact=(
                f"The plain-HTTP request for {report.host} was redirected to a "
                f"different host ({plain.final_host}) after {plain.redirects} "
                "redirect(s)."
            ),
            possible_causes=[
                "A captive portal is intercepting web requests until the user signs in (a suspicion, not a certainty).",
                "The site itself redirects its plain-HTTP traffic to another host.",
            ],
            recommendations=[
                "Open a plain-HTTP page in a browser and see whether a sign-in or notice page appears.",
                "If a portal sign-in exists, complete it and run the check again.",
            ],
            confidence="low",
        ))
    return out
