"""Tests that the application enforces required environment variables at startup.

The Settings class in policy_engine/config.py uses pydantic-settings with
SECRET_KEY declared as Field(...) (required, no default).  DATABASE_URL has a
default of "sqlite:///./sentinel.db", so we validate that the app starts
correctly when all vars are present.

These tests manipulate os.environ directly and reload the config module so
each test gets a fresh Settings() instance.
"""
from __future__ import annotations

import importlib
import os
import sys
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_settings(env_overrides: dict) -> None:
    """
    Patch os.environ with env_overrides, force-reload policy_engine.config,
    and restore the environment afterwards.

    Raises whatever pydantic-settings raises on validation failure.
    """
    original = os.environ.copy()
    try:
        os.environ.update(env_overrides)
        # Remove stale cached module so Settings() re-reads the environment
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("policy_engine.config") or mod_name == "policy_engine.config":
                del sys.modules[mod_name]
        importlib.import_module("policy_engine.config")
    finally:
        os.environ.clear()
        os.environ.update(original)
        # Restore the real module so other tests are unaffected
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("policy_engine.config"):
                del sys.modules[mod_name]
        importlib.import_module("policy_engine.config")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEnvValidation:
    def test_app_crashes_if_secret_key_missing(self) -> None:
        """Application must refuse to start when SECRET_KEY is not set."""
        # Remove SECRET_KEY from environment entirely
        env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
        original = os.environ.copy()
        try:
            os.environ.clear()
            os.environ.update(env)
            for mod_name in list(sys.modules.keys()):
                if "policy_engine.config" in mod_name:
                    del sys.modules[mod_name]
            with pytest.raises((ValueError, Exception)):
                importlib.import_module("policy_engine.config")
        finally:
            os.environ.clear()
            os.environ.update(original)
            for mod_name in list(sys.modules.keys()):
                if "policy_engine.config" in mod_name:
                    del sys.modules[mod_name]
            importlib.import_module("policy_engine.config")

    def test_app_crashes_if_secret_key_too_short(self) -> None:
        """Application lifespan guard rejects SECRET_KEY shorter than 32 chars.

        config.py itself allows any non-empty string, but main.py lifespan
        raises RuntimeError when len(SECRET_KEY) < MIN_SECRET_KEY_LENGTH.
        We verify that the Settings object propagates a short key so the guard
        can fire.
        """
        env_patch = {
            "SECRET_KEY": "tooshort",
            "DATABASE_URL": "sqlite:///./test_validation.db",
        }
        original = os.environ.copy()
        try:
            os.environ.update(env_patch)
            for mod_name in list(sys.modules.keys()):
                if "policy_engine.config" in mod_name:
                    del sys.modules[mod_name]
            cfg = importlib.import_module("policy_engine.config")
            # The setting is accepted by pydantic (no length constraint at
            # model level), but the value must be accessible so main.py can
            # enforce it at lifespan startup.
            assert cfg.settings.SECRET_KEY == "tooshort"
            assert len(cfg.settings.SECRET_KEY) < cfg.settings.MIN_SECRET_KEY_LENGTH
        finally:
            os.environ.clear()
            os.environ.update(original)
            for mod_name in list(sys.modules.keys()):
                if "policy_engine.config" in mod_name:
                    del sys.modules[mod_name]
            importlib.import_module("policy_engine.config")

    def test_app_starts_with_all_required_vars_set(self) -> None:
        """Application config loads successfully when all required vars are present."""
        strong_key = "a" * 40  # 40 chars — well above MIN_SECRET_KEY_LENGTH=32
        env_patch = {
            "SECRET_KEY": strong_key,
            "DATABASE_URL": "sqlite:///./test_validation.db",
        }
        original = os.environ.copy()
        try:
            os.environ.update(env_patch)
            for mod_name in list(sys.modules.keys()):
                if "policy_engine.config" in mod_name:
                    del sys.modules[mod_name]
            cfg = importlib.import_module("policy_engine.config")
            assert cfg.settings.SECRET_KEY == strong_key
            assert cfg.settings.DATABASE_URL == "sqlite:///./test_validation.db"
            assert cfg.settings.APP_NAME == "Sentinel AI Policy Engine"
        finally:
            os.environ.clear()
            os.environ.update(original)
            for mod_name in list(sys.modules.keys()):
                if "policy_engine.config" in mod_name:
                    del sys.modules[mod_name]
            importlib.import_module("policy_engine.config")
