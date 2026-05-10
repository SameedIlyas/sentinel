"""Auto-mark legacy phase tests as ``regression`` without editing source files.

The Phase 6 plan calls for ``@pytest.mark.regression`` on existing
phase0..phase7 tests so CI can run ``pytest -m regression`` to gate on
the historical suite. Editing 30+ test files just to add a module-level
mark is risky and noisy; a collection hook does it once.

Loaded by tests/conftest.py via ``pytest_collection_modifyitems`` in the
same module — see end of conftest.py.
"""
