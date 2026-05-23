"""SSRF defence for outbound webhook URLs (audit finding R4).

The webhook subscription surface lets an admin point the platform at
an arbitrary ``target_url``. Without a guard, that admin can drive
the dispatch worker — which has unrestricted egress inside the
deployment network — at internal services: Redis at ``redis:6379``,
Postgres at ``db:5432``, the cloud metadata endpoint
``169.254.169.254``, or any other private resource that happens to
accept a JSON POST.

This module provides one entry point — :func:`assert_url_safe` —
that the create handler calls at subscription time and the dispatch
worker calls again immediately before the POST. The dispatch-time
check defeats DNS rebinding (the address recorded at create time
may not be the address resolved at dispatch).

What we refuse:
  * Non-``http``/``https`` schemes (file://, gopher://, etc.).
  * URLs without a hostname.
  * Numeric IP literals that fall in a non-public range
    (loopback, link-local, multicast, private, reserved,
    unspecified, broadcast).
  * Hostnames whose DNS resolution returns *any* address in those
    ranges. We refuse on the first private hit so a public-A /
    private-AAAA pair still trips us.

What we don't (yet) do:
  * Bind the outbound socket to the resolved IP. There's a small
    TOCTOU window between this resolve and httpx's resolve; closing
    it requires a custom transport. Tracked as a follow-up for an
    SSRF-hardening sprint.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Iterable
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    """Raised when a webhook ``target_url`` fails the SSRF guard."""


_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True iff ``ip`` is a routable, non-special address."""

    return not (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_private
        or ip.is_reserved
        or ip.is_unspecified
        # ``is_global`` is the canonical check for "publicly routable"
        # but it's lenient on IPv6 doc / mapped ranges. The disjunctive
        # above is the safe-by-default form.
    )


def _resolve(host: str) -> Iterable[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Yield every resolved IP for ``host``.

    Wraps :func:`socket.getaddrinfo` and filters down to the unique
    sockaddr addresses across all returned A/AAAA records.
    """

    seen: set[str] = set()
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"hostname {host!r} did not resolve") from exc

    for family, _socktype, _proto, _canon, sockaddr in infos:
        # sockaddr is (host, port) for v4 and (host, port, flowinfo, scopeid) for v6.
        addr = sockaddr[0]
        if addr in seen:
            continue
        seen.add(addr)
        try:
            yield ipaddress.ip_address(addr)
        except ValueError:
            # Should not happen for getaddrinfo output; refuse to be
            # safe if it ever does.
            raise UnsafeUrlError(f"unrecognised address {addr!r} for {host!r}")


def assert_url_safe(url: str) -> None:
    """Refuse ``url`` if any check fails.

    On success: returns ``None``.
    On failure: raises :class:`UnsafeUrlError` with a redacted
    detail safe to surface to API clients (no internal IP leak).
    """

    if not url or not isinstance(url, str):
        raise UnsafeUrlError("target_url is required")

    parsed = urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError("target_url scheme must be http or https")
    if not parsed.hostname:
        raise UnsafeUrlError("target_url must include a hostname")

    host = parsed.hostname

    # If the URL itself carries an IP literal, validate that
    # directly without a DNS round-trip — saves a syscall for the
    # common literal-IP block case.
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        if not _is_public(literal):
            raise UnsafeUrlError(
                "target_url IP is not publicly routable"
            )
        return

    # Hostname path — resolve, refuse if any address is non-public.
    addresses = list(_resolve(host))
    if not addresses:
        raise UnsafeUrlError(f"hostname {host!r} did not resolve")

    for ip in addresses:
        if not _is_public(ip):
            raise UnsafeUrlError(
                "target_url hostname resolves to a non-public address"
            )


__all__ = ["UnsafeUrlError", "assert_url_safe"]
