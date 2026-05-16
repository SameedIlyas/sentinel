"""Smoke test for the SECRET_KEY / CORS startup guards (main.py:84-96).

These guards were not touched in this remediation pass, but the regression
check in the verification loop demands proof they still abort. We import
the lifespan generator directly and drive it with overridden settings.
"""

import asyncio
from unittest.mock import patch

import pytest

from policy_engine import main


def _drive_lifespan() -> None:
    cm = main.lifespan(main.app)
    asyncio.run(_advance(cm))


async def _advance(cm) -> None:
    async with cm:
        return


def test_lifespan_rejects_empty_secret_key():
    with patch.object(main.settings, "SECRET_KEY", ""):
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            _drive_lifespan()


def test_lifespan_rejects_short_secret_key():
    with patch.object(main.settings, "SECRET_KEY", "shortkey"), patch.object(
        main.settings, "MIN_SECRET_KEY_LENGTH", 32
    ):
        with pytest.raises(RuntimeError, match="at least 32 characters"):
            _drive_lifespan()


def test_lifespan_rejects_known_weak_default():
    weak = next(iter(main._WEAK_KEYS))
    with patch.object(main.settings, "SECRET_KEY", weak), patch.object(
        main.settings, "MIN_SECRET_KEY_LENGTH", 1
    ):
        with pytest.raises(RuntimeError, match="weak default"):
            _drive_lifespan()


def test_lifespan_rejects_cors_wildcard_in_production():
    with patch.object(main.settings, "CORS_ALLOW_ALL_ORIGINS", True), patch.object(
        main.settings, "APP_ENV", "production"
    ):
        with pytest.raises(RuntimeError, match="CORS_ALLOW_ALL_ORIGINS"):
            _drive_lifespan()
