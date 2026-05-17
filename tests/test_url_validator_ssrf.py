"""Regression tests for the SSRF guard's IPv6 blocklist (REVIEW.md HIGH-032).

Before the fix only ``::1/128`` was blocked. The fix adds the ULA, link-local,
IPv4-mapped, NAT64 and Discard ranges (and a multicast check) to
``_is_private_ip`` so DNS records that resolve to internal IPv6 addresses
can no longer bypass the validator.
"""

import pytest

from policy_engine.services.url_validator import _is_private_ip


@pytest.mark.parametrize(
    "addr",
    [
        # IPv4 private ranges — pre-existing coverage, retained for regression.
        "127.0.0.1",
        "10.0.0.1",
        "172.16.5.1",
        "192.168.1.1",
        "169.254.169.254",  # AWS IMDS
        # IPv6 loopback (pre-existing).
        "::1",
        # ULA — fc00::/7.
        "fc00::1",
        "fd00::1",
        "fdab:1234::1",
        # Link-local — fe80::/10.
        "fe80::1",
        "fe80::abcd:1234",
        # IPv4-mapped IPv6 — ::ffff:0:0/96 (maps every IPv4 private range).
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "::ffff:169.254.169.254",
        # NAT64 — 64:ff9b::/96 (used to embed IPv4 into IPv6).
        "64:ff9b::a00:1",
        # Multicast — ff00::/8.
        "ff02::1",
    ],
)
def test_private_ips_are_blocked(addr: str) -> None:
    assert _is_private_ip(addr) is True, f"{addr} should be flagged as private"


@pytest.mark.parametrize(
    "addr",
    [
        "8.8.8.8",
        "1.1.1.1",
        "2001:4860:4860::8888",  # Google public DNS over IPv6.
    ],
)
def test_public_ips_are_allowed(addr: str) -> None:
    assert _is_private_ip(addr) is False, f"{addr} should be allowed"
