"""Sentinel SDK: client-side shadow-AI self-reporting (Path C).

Tier 3 — when an application that uses the Sentinel SDK calls an LLM provider
that is not in the explicit allowlist, the SDK fires a detection back to the
Sentinel server's `/v1/admin/shadow-ai/ingest` endpoint. Lets governance
teams catch the case where a developer wires up a new model/provider that
hasn't been approved yet — even when the provider sits behind the SDK
itself.

Roadmap caveat: Path C only catches developers who already use the SDK.
That's intentional — it's complementary to network-side ingestion (Path A),
not a replacement. It's also the fastest path to a working "shadow AI"
detection in environments where Sentinel is the LLM gateway.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ShadowAIConfig:
    api_url: str = ""
    api_key: str = ""
    allowed_providers: Set[str] = field(default_factory=set)
    department: str = ""
    request_timeout_seconds: float = 5.0
    enabled: bool = True
    # In-memory dedup: skip detections we already reported within this window
    dedup_window_seconds: float = 600.0


@dataclass(frozen=True)
class ShadowAIDetection:
    destination_host: str
    destination_port: int
    provider_name: str
    method: Optional[str]
    user_agent: Optional[str]
    bytes_transferred: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

class _ShadowAIReporter:
    """Reports non-allowlisted provider calls to the Sentinel server."""

    def __init__(self, config: Optional[ShadowAIConfig] = None) -> None:
        self._config = config or ShadowAIConfig()
        self._recent: Dict[str, float] = {}
        self._lock = threading.Lock()
        self.posted_count = 0
        self.skipped_dedup = 0
        self.skipped_allowlisted = 0
        self.failed_count = 0

    @property
    def config(self) -> ShadowAIConfig:
        return self._config

    def update_config(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if not hasattr(self._config, key):
                continue
            if key == "allowed_providers":
                if isinstance(value, (list, tuple, set)):
                    setattr(self._config, key, {str(v).lower() for v in value})
                continue
            setattr(self._config, key, value)

    def is_provider_allowed(self, provider_name: str) -> bool:
        provider_lc = (provider_name or "").lower()
        return provider_lc in self._config.allowed_providers

    def report_provider_call(
        self,
        *,
        provider_name: str,
        endpoint: str,
        method: str = "POST",
        user_agent: Optional[str] = None,
        bytes_transferred: int = 0,
    ) -> bool:
        """If the provider is not allowlisted, report it. Returns True if reported."""
        if not self._config.enabled:
            return False
        if self.is_provider_allowed(provider_name):
            self.skipped_allowlisted += 1
            return False

        host, port = _split_host_and_port(endpoint)
        if not host:
            return False

        # Dedup: skip if we already reported the same (provider, host) recently
        dedup_key = f"{provider_name.lower()}::{host.lower()}"
        now = time.monotonic()
        with self._lock:
            last = self._recent.get(dedup_key)
            if last is not None and (now - last) < self._config.dedup_window_seconds:
                self.skipped_dedup += 1
                return False
            self._recent[dedup_key] = now

        detection = ShadowAIDetection(
            destination_host=host,
            destination_port=port,
            provider_name=provider_name,
            method=method,
            user_agent=user_agent,
            bytes_transferred=bytes_transferred,
        )
        return self._post(detection)

    def _post(self, detection: ShadowAIDetection) -> bool:
        if not (self._config.api_url and self._config.api_key):
            logger.debug(
                "shadow_ai SDK not fully configured — skipping report (host=%s)",
                detection.destination_host,
            )
            return False
        try:
            import httpx
        except ImportError:
            return False

        url = self._config.api_url.rstrip("/") + "/v1/admin/shadow-ai/ingest"
        body = {
            "records": [{
                "destination_host": detection.destination_host,
                "destination_port": detection.destination_port,
                "method": detection.method,
                "user_agent": detection.user_agent,
                "bytes_transferred": detection.bytes_transferred,
                "department": self._config.department or None,
                "timestamp": detection.timestamp,
            }],
        }
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self._config.api_key,
        }
        try:
            with httpx.Client(timeout=self._config.request_timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=body)
            if resp.is_success:
                self.posted_count += 1
                return True
            self.failed_count += 1
            logger.warning(
                "shadow_ai SDK report rejected: %s %s",
                resp.status_code, resp.text[:200],
            )
            return False
        except Exception as exc:
            self.failed_count += 1
            logger.warning("shadow_ai SDK report failed: %s", exc)
            return False


def _split_host_and_port(endpoint: str) -> tuple:
    """Extract (host, port) from a URL or bare host:port string."""
    if not endpoint:
        return "", 443
    if "://" in endpoint:
        parsed = urlparse(endpoint)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return host, port
    if ":" in endpoint:
        host, _, port_s = endpoint.partition(":")
        try:
            return host, int(port_s)
        except ValueError:
            return host, 443
    return endpoint, 443


# ---------------------------------------------------------------------------
# Module-level convenience API — single global reporter
# ---------------------------------------------------------------------------

_reporter: Optional[_ShadowAIReporter] = None
_reporter_lock = threading.Lock()


def _get_reporter() -> _ShadowAIReporter:
    global _reporter
    with _reporter_lock:
        if _reporter is None:
            _reporter = _ShadowAIReporter()
    return _reporter


def configure(
    *,
    api_url: str = "",
    api_key: str = "",
    allowed_providers: Iterable[str] = (),
    department: str = "",
    request_timeout_seconds: float = 5.0,
    dedup_window_seconds: float = 600.0,
    enabled: bool = True,
) -> None:
    """Configure the SDK shadow-AI reporter once at app startup."""
    _get_reporter().update_config(
        api_url=api_url,
        api_key=api_key,
        allowed_providers=set(allowed_providers),
        department=department,
        request_timeout_seconds=request_timeout_seconds,
        dedup_window_seconds=dedup_window_seconds,
        enabled=enabled,
    )


def is_provider_allowed(provider_name: str) -> bool:
    return _get_reporter().is_provider_allowed(provider_name)


def report_provider_call(
    *,
    provider_name: str,
    endpoint: str,
    method: str = "POST",
    user_agent: Optional[str] = None,
    bytes_transferred: int = 0,
) -> bool:
    """Detect + (if non-allowlisted) report an LLM provider call.

    Intended call site: inside `ToolCallInterceptor.before_request` or
    equivalent — wherever the SDK already sees the outbound LLM URL.

    Returns True if a detection was POSTed, False if allowlisted, deduped,
    disabled, or unreachable.
    """
    return _get_reporter().report_provider_call(
        provider_name=provider_name,
        endpoint=endpoint,
        method=method,
        user_agent=user_agent,
        bytes_transferred=bytes_transferred,
    )


def reset_for_tests() -> None:
    """Test-only — drop the cached reporter."""
    global _reporter
    with _reporter_lock:
        _reporter = None
