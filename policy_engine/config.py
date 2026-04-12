"""Configuration settings for Policy Engine"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List


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

    # Audit log archival
    ARCHIVE_BACKEND: str = "local"          # "local" | "s3"
    ARCHIVE_LOCAL_PATH: str = ""            # required when ARCHIVE_BACKEND=local
    ARCHIVE_S3_BUCKET: str = ""             # required when ARCHIVE_BACKEND=s3
    ARCHIVE_S3_PREFIX: str = "audit-logs/"
    ARCHIVE_S3_KMS_KEY_ID: str = ""         # KMS key ARN/alias; empty = bucket default

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
