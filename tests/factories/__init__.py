"""Test data factories for the clinic-tier test suite.

All factories produce **PHI-safe synthetic data** per HIPAA Safe Harbor
(45 CFR 164.514(b)(2)). Free-text fields must NEVER match any pattern in
``policy_engine.services.phi_text_check._PATTERNS``. Anything written here
is committed to git, so a leaked identifier is a permanent record breach.

Two scanners gate this contract:
* ``phi_text_check.scan_for_phi`` (in-tree, regex-based)
* ``presidio-analyzer`` (external, ML-based — Phase 7)
"""
