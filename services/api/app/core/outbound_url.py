from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from .settings import Settings, get_settings


def validate_outbound_url(url: str, settings: Settings | None = None, *, purpose: str = "outbound request") -> str:
    """Reject unsafe tenant-configured URLs before any network request.

    This is application-level defence. Production deployments must also enforce
    egress policy and DNS controls so DNS rebinding cannot reach metadata or
    private infrastructure.
    """

    settings = settings or get_settings()
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError(f"{purpose} must use HTTP or HTTPS.")
    if parsed.scheme == "http" and not settings.outbound_http_allow_insecure:
        raise ValueError(f"{purpose} must use HTTPS.")
    if not parsed.hostname:
        raise ValueError(f"{purpose} must include a host name.")
    if parsed.username or parsed.password:
        raise ValueError(f"{purpose} must not contain embedded credentials.")

    hostname = parsed.hostname.rstrip(".").lower()
    allowed = {item.strip().lower() for item in settings.outbound_http_allowed_hosts.split(",") if item.strip()}
    if allowed and not any(hostname == item or hostname.endswith(f".{item}") for item in allowed):
        raise ValueError(f"{purpose} host is not in the configured outbound allowlist.")

    if hostname in {"localhost", "localhost.localdomain"} and not settings.outbound_http_allow_private_networks:
        raise ValueError(f"{purpose} cannot target localhost.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ) and not settings.outbound_http_allow_private_networks:
        raise ValueError(f"{purpose} cannot target a private or special-use address.")
    return url
