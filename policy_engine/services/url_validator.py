"""SSRF-safe URL validation for external HTTP calls."""
import ipaddress
import os
import re
import socket
from typing import List, Tuple
from urllib.parse import urlparse

GITHUB_URL_PATTERN = re.compile(
    r'^https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$'
)

PRIVATE_RANGES: List[ipaddress.IPv4Network] = [
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("169.254.0.0/16"),
]

PRIVATE_IPV6: List[ipaddress.IPv6Network] = [
    ipaddress.IPv6Network("::1/128"),       # Loopback
    ipaddress.IPv6Network("fc00::/7"),      # Unique Local Addresses (RFC 4193)
    ipaddress.IPv6Network("fe80::/10"),     # Link-local (RFC 4291)
    ipaddress.IPv6Network("::ffff:0:0/96"), # IPv4-mapped IPv6 (covers all RFC 1918 + IMDS)
    ipaddress.IPv6Network("64:ff9b::/96"),  # NAT64 (RFC 6052)
    ipaddress.IPv6Network("100::/64"),      # Discard prefix (RFC 6666)
]

ALLOWED_PORTS = {80, 443}


class SSRFBlockedError(ValueError):
    """Raised when a URL is blocked due to SSRF risk."""


def validate_github_url(url: str) -> Tuple[str, str]:
    """Validate a GitHub repository URL and return (owner, repo).

    Args:
        url: URL to validate.

    Returns:
        Tuple of (owner, repo) extracted from the URL.

    Raises:
        ValueError: If the URL does not match the expected GitHub format.
    """
    match = GITHUB_URL_PATTERN.match(url)
    if not match:
        raise ValueError("Invalid GitHub repository URL")
    return match.group(1), match.group(2)


def _is_private_ip(addr: str) -> bool:
    """Return True if addr is a private/internal IP address."""
    try:
        ip = ipaddress.ip_address(addr)
        if isinstance(ip, ipaddress.IPv4Address):
            return any(ip in net for net in PRIVATE_RANGES)
        if isinstance(ip, ipaddress.IPv6Address):
            if ip.is_multicast:
                return True
            return any(ip in net for net in PRIVATE_IPV6)
    except ValueError:
        pass
    return False


def validate_external_url(url: str) -> str:
    """Validate a URL for SSRF safety before making external HTTP calls.

    Resolves DNS first to prevent DNS-rebinding attacks, then checks all
    resolved IPs against private/internal ranges.

    Args:
        url: URL to validate.

    Returns:
        The original validated URL (safe to use for HTTP calls).

    Raises:
        SSRFBlockedError: If the URL poses an SSRF risk.
    """
    # 1. Scheme check — only http/https allowed
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    if scheme not in ("http", "https"):
        raise SSRFBlockedError("Only http and https schemes are allowed")

    # 2. Parse URL
    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise SSRFBlockedError("URL has no resolvable hostname")

    # 3. Resolve DNS FIRST (anti-DNS-rebinding)
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise SSRFBlockedError("DNS resolution failed")

    # 4. Check ALL resolved IPs against private ranges
    for info in addr_infos:
        ip_str = info[4][0]
        if _is_private_ip(ip_str):
            raise SSRFBlockedError("Private/internal IP addresses are not allowed")

    # 5. Port check
    allow_custom = os.environ.get("MLFLOW_ALLOW_CUSTOM_PORT", "").lower() == "true"
    port = parsed.port
    if not allow_custom and port is not None and port not in ALLOWED_PORTS:
        raise SSRFBlockedError("Only ports 80 and 443 are allowed")

    # 6. Return the original validated URL
    return url
