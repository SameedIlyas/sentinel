"""Fernet (AES-256) column-level encryption service and SQLAlchemy TypeDecorator."""

import json
import logging
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)


class EncryptionService:
    """AES-256 (Fernet) symmetric encryption for sensitive column values."""

    def __init__(self, key: bytes):
        self._fernet = Fernet(key)

    @staticmethod
    def generate_key() -> bytes:
        """Generate a new random 32-byte Fernet key."""
        return Fernet.generate_key()

    def encrypt(self, value: Any) -> Optional[str]:
        """Encrypt a value. Returns base64url string or None for None input."""
        if value is None:
            return None
        if not isinstance(value, str):
            value = json.dumps(value)
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: Optional[str]) -> Optional[str]:
        """Decrypt a value. Returns plaintext string or None for None input."""
        if value is None:
            return None
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except (InvalidToken, Exception) as e:
            logger.error("Decryption failed: %s", e)
            raise


def _get_default_service() -> Optional[EncryptionService]:
    """Return a module-level EncryptionService built from ENCRYPTION_KEY env var."""
    try:
        import os
        key = os.environ.get("ENCRYPTION_KEY")
        if key:
            return EncryptionService(key.encode())
    except Exception:
        pass
    return None


class EncryptedString(TypeDecorator):
    """SQLAlchemy TypeDecorator that transparently encrypts/decrypts string columns."""

    impl = String
    cache_ok = True

    def __init__(self, service: Optional[EncryptionService] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._service = service or _get_default_service()

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        """Encrypt on write."""
        if value is None or self._service is None:
            return value
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return self._service.encrypt(str(value))

    def process_result_value(self, value: Optional[str], dialect) -> Any:
        """Decrypt on read."""
        if value is None or self._service is None:
            return value
        try:
            decrypted = self._service.decrypt(value)
            try:
                return json.loads(decrypted)
            except (json.JSONDecodeError, TypeError):
                return decrypted
        except Exception:
            return value  # Return ciphertext rather than crash on legacy data
