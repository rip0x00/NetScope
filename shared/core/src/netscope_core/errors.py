"""Shared socket-error classification.

Every probe maps the exceptions it catches through
:func:`classify_socket_error`, so a connection reset means the same
thing in a DNS, TCP, TLS and HTTP result. Exception classes are checked
before errno values because the classes are consistent across platforms
while errno numbering is not; the errno table therefore lists POSIX and
Winsock values side by side (the ``errno`` module does not define the
WSA* names on POSIX systems, so the numbers are written literally).

Internal kinds are short strings ("reset", "refused", ...). The report
schema uses a different vocabulary; :func:`schema_error_kind` converts.
"""

from __future__ import annotations

import socket

# Winsock error codes (Windows) alongside their POSIX counterparts.
_RESET_ERRNOS = {104, 10054, 103, 10053}        # ECONNRESET, WSAECONNRESET, ECONNABORTED, WSAECONNABORTED
_REFUSED_ERRNOS = {111, 10061}                 # ECONNREFUSED, WSAECONNREFUSED
_UNREACHABLE_ERRNOS = {101, 113, 10051, 10065}  # ENETUNREACH, EHOSTUNREACH, WSAENETUNREACH, WSAEHOSTUNREACH
_TIMEOUT_ERRNOS = {110, 10060}                 # ETIMEDOUT, WSAETIMEDOUT
_PERMISSION_ERRNOS = {1, 13}                   # EPERM, EACCES


def classify_socket_error(exc: BaseException) -> str:
    """Map a socket-related exception to a short, portable error kind.

    Returns one of: "reset", "refused", "timeout", "unreachable",
    "dns", "permission", "error".
    """
    if isinstance(exc, ConnectionResetError):
        return "reset"
    if isinstance(exc, ConnectionRefusedError):
        return "refused"
    if isinstance(exc, ConnectionAbortedError):
        return "reset"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, socket.gaierror):
        return "dns"
    if isinstance(exc, PermissionError):
        return "permission"
    if isinstance(exc, OSError):
        err_no = exc.errno
        if err_no in _RESET_ERRNOS:
            return "reset"
        if err_no in _REFUSED_ERRNOS:
            return "refused"
        if err_no in _UNREACHABLE_ERRNOS:
            return "unreachable"
        if err_no in _TIMEOUT_ERRNOS:
            return "timeout"
        if err_no in _PERMISSION_ERRNOS:
            return "permission"
    return "error"


_SCHEMA_KINDS = {
    "reset": "connection_reset",
    "refused": "connection_refused",
    "timeout": "timeout",
    "unreachable": "network_unreachable",
    "dns": "dns_failure",
    "certificate": "tls_failure",
    "permission": "permission_denied",
    "error": "unknown",
}


def schema_error_kind(kind: str | None, check: str = "") -> str:
    """Convert an internal error kind to the report schema's vocabulary.

    The schema has no generic protocol-error kind: protocol failures in
    the TLS check are reported as ``tls_failure``; in any other check
    they are ``unknown``.
    """
    if kind == "protocol":
        return "tls_failure" if check == "tls" else "unknown"
    return _SCHEMA_KINDS.get(kind or "error", "unknown")
