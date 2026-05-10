"""SDK harness tests (Phase 4).

Anthropic Messages API + internal Sentinel SDK adapters. All HTTP traffic
is intercepted via ``respx`` — zero real network calls. ``pytest-recording``
is intentionally absent because cassettes risk PHI capture.
"""
