"""JWT token utilities for user authentication"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import uuid
import jwt
from passlib.context import CryptContext

from policy_engine.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Default values that must never be used in production
_DEFAULT_SECRETS = {
    "change-me-in-production",
    "your-secret-key-change-this-in-production",
}


def validate_secret_key_for_production(app_env: str, secret_key: str) -> None:
    """
    Validate that the SECRET_KEY is not a default/weak value in production.

    Args:
        app_env: The application environment (e.g. 'production', 'development')
        secret_key: The configured SECRET_KEY value

    Raises:
        ValueError: If running in production with a default or empty SECRET_KEY
    """
    if app_env.lower() == "production":
        if not secret_key or secret_key in _DEFAULT_SECRETS:
            raise ValueError(
                "SECRET_KEY must be set to a strong, random value in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in the token (typically user_id, username, role)
        expires_delta: Token expiration time delta (default: settings value)

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4()),
        "iss": "sentinel",
        "aud": "sentinel-api",
    })

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded token data if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except (jwt.PyJWTError, jwt.DecodeError, jwt.InvalidTokenError, Exception):
        return None


def get_token_expiration_time() -> int:
    """
    Get the token expiration time in seconds.

    Returns:
        Expiration time in seconds
    """
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)
