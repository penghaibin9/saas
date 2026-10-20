"""Canonicalize forwarded headers once, before the frozen context middleware.

An edge proxy must replace caller-supplied forwarding headers. For trusted
multi-hop deployments, walk right-to-left and select the nearest untrusted hop.
Invalid, duplicate or overlong chains never become a trusted identity.
"""
from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Iterable

_MAX_HOPS = 16
_MAX_HEADER_BYTES = 4096
_FORWARDING = {b"x-forwarded-for", b"x-real-ip", b"x-forwarded-proto",
               b"x-forwarded-host", b"forwarded"}


def _address(value: str):
    value = str(value or "").strip()
    if not value or len(value) > 64 or "%" in value:
        return None
    try:
        result = ipaddress.ip_address(value)
        return result.ipv4_mapped if isinstance(result, ipaddress.IPv6Address) and result.ipv4_mapped else result
    except ValueError:
        return None


@lru_cache(maxsize=16)
def _networks(spec: str) -> tuple:
    result = []
    for part in str(spec or "").split(","):
        try:
            result.append(ipaddress.ip_network(part.strip(), strict=False))
        except ValueError:
            continue  # invalid configuration never broadens trust
    return tuple(result)


def _trusted(address, spec: str) -> bool:
    return address is not None and any(address in net for net in _networks(spec))


def canonical_client_ip(direct: str, xff: Iterable[str], real: Iterable[str], trusted_spec: str) -> str:
    peer = _address(direct)
    direct_value = str(peer) if peer is not None else str(direct or "")[:64]
    if not _trusted(peer, trusted_spec):
        return direct_value
    forwarded, real_values = list(xff), list(real)
    if len(forwarded) > 1:
        return direct_value
    if forwarded:
        raw = forwarded[0]
        if len(raw.encode("utf-8")) > _MAX_HEADER_BYTES:
            return direct_value
        parts = raw.split(",")
        if not parts or len(parts) > _MAX_HOPS:
            return direct_value
        addresses = [_address(part) for part in parts]
        if any(address is None for address in addresses):
            return direct_value
        for address in reversed(addresses):
            if not _trusted(address, trusted_spec):
                return str(address)
        return direct_value  # all-trusted chain is ambiguous; do not pick caller's first item
    if len(real_values) == 1:
        result = _address(real_values[0])
        if result is not None:
            return str(result)
    return direct_value


def normalize_forwarded_request(request, trusted_spec: str) -> None:
    # Accessing headers makes Starlette cache the same mutable list as scope.
    # Mutating that list in place keeps cached request.headers and downstream
    # ASGI scope consistent; no monkeypatch of global middleware functions.
    headers = request.headers
    direct = request.client.host if request.client else ""
    trusted_peer = _trusted(_address(direct), trusted_spec)
    ip = canonical_client_ip(direct, headers.getlist("x-forwarded-for"),
                             headers.getlist("x-real-ip"), trusted_spec)
    proto_values = headers.getlist("x-forwarded-proto")
    proto = proto_values[0].strip().lower() if trusted_peer and len(proto_values) == 1 else ""
    raw = request.scope["headers"]
    normalized = [(key, value) for key, value in raw if key.lower() not in _FORWARDING]
    if trusted_peer and _address(ip) is not None:
        normalized.extend([(b"x-forwarded-for", ip.encode("ascii")), (b"x-real-ip", ip.encode("ascii"))])
    if proto in {"http", "https"}:
        normalized.append((b"x-forwarded-proto", proto.encode("ascii")))
        request.scope["scheme"] = proto
    raw[:] = normalized
