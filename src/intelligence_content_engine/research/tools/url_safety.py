"""Outbound URL safety checks for research fetchers.

The engine follows URLs discovered from search engines and sitemaps. These URLs
are untrusted input, so network fetchers must reject local/private destinations
and non-HTTP schemes before making outbound requests.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    """Raised when a URL is not safe for outbound fetching."""


def validate_outbound_url(url: str) -> str:
    """Validate and return a normalized HTTP(S) URL.

    Blocks localhost, loopback, link-local, private, multicast, reserved and
    unspecified IP addresses, including hostnames that resolve to them.
    """
    if not isinstance(url, str) or not url.strip():
        raise UnsafeURLError("URL must be a non-empty string")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURLError("Only HTTP and HTTPS URLs are allowed")
    if not parsed.hostname:
        raise UnsafeURLError("URL must contain a hostname")
    if parsed.username or parsed.password:
        raise UnsafeURLError("URLs containing embedded credentials are not allowed")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"}:
        raise UnsafeURLError("Localhost is not allowed")

    try:
        ip = ipaddress.ip_address(hostname)
        if _is_unsafe_ip(ip):
            raise UnsafeURLError(f"Private or reserved destination is not allowed: {hostname}")
    except ValueError:
        try:
            addresses = {
                info[4][0]
                for info in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            }
        except socket.gaierror as exc:
            raise UnsafeURLError(f"Hostname could not be resolved: {hostname}") from exc
        if not addresses:
            raise UnsafeURLError(f"Hostname could not be resolved: {hostname}")
        for address in addresses:
            try:
                if _is_unsafe_ip(ipaddress.ip_address(address)):
                    raise UnsafeURLError(f"Hostname resolves to a private or reserved destination: {hostname}")
            except ValueError:
                raise UnsafeURLError(f"Invalid resolved address for hostname: {hostname}") from None

    return parsed.geturl()


def _is_unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )
