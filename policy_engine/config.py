"""Configuration settings for Policy Engine"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "Sentinel AI Policy Engine"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_ALL_ORIGINS: bool = False
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Database
    DATABASE_URL: str = "sqlite:///./sentinel.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 300  # 5 minutes

    # API
    API_KEY_HEADER: str = "X-API-Key"
    RATE_LIMIT_PER_MINUTE: int = 1000

    # Security — SECRET_KEY has no default; must be supplied via env or .env file
    SECRET_KEY: str = Field(...)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    MIN_SECRET_KEY_LENGTH: int = 32
    ALLOWED_AUDIENCES: List[str] = ["sentinel-api"]

    # Application environment
    APP_ENV: str = "development"

    # ── Session cookie (CRIT-011) ─────────────────────────────────────
    # The access token is delivered as an HttpOnly Secure SameSite cookie
    # so XSS cannot exfiltrate the bearer token. The CSRF token is a
    # second, JS-readable cookie used in the double-submit check; see
    # policy_engine/middleware/csrf.py.
    SESSION_COOKIE_NAME: str = "access_token"
    # Secure attribute defaults to ON in production and OFF in dev so
    # local HTTP traffic still works without HTTPS.
    SESSION_COOKIE_SECURE: Optional[bool] = None
    # SameSite=lax keeps the cookie out of cross-origin POSTs while
    # preserving top-level navigation. CSRF middleware enforces the
    # double-submit check on mutating requests so 'lax' is sufficient.
    SESSION_COOKIE_SAMESITE: str = "lax"
    # Empty Domain → host-only cookie, which is correct for first-party
    # SPA deployments. Set explicitly for staging / subdomain layouts.
    SESSION_COOKIE_DOMAIN: str = ""
    SESSION_COOKIE_PATH: str = "/"

    # Audit log archival
    ARCHIVE_BACKEND: str = "local"          # "local" | "s3"
    ARCHIVE_LOCAL_PATH: str = ""            # required when ARCHIVE_BACKEND=local
    ARCHIVE_S3_BUCKET: str = ""             # required when ARCHIVE_BACKEND=s3
    ARCHIVE_S3_PREFIX: str = "audit-logs/"
    ARCHIVE_S3_KMS_KEY_ID: str = ""         # KMS key ARN/alias; empty = bucket default

    # GitHub Integration
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    GITHUB_REQUEST_TIMEOUT_SECONDS: int = 10

    # MLflow Integration
    MLFLOW_TRACKING_URI: Optional[str] = None
    MLFLOW_REQUEST_TIMEOUT_SECONDS: int = 10
    MLFLOW_ALLOW_CUSTOM_PORT: bool = False

    # DICOM Integration
    DICOM_MAX_FILE_SIZE_MB: int = 50

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
