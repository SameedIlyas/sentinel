"""Database configuration — sync (legacy/tests) + async (production routes)."""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from policy_engine.config import settings


# ---------------------------------------------------------------------------
# Async engine (default for all route handlers)
# ---------------------------------------------------------------------------

def _make_async_url(url: str) -> str:
    """Convert a DATABASE_URL to its async driver equivalent."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


_async_url = _make_async_url(settings.DATABASE_URL)

if _async_url.startswith("sqlite"):
    async_engine = create_async_engine(
        _async_url,
        connect_args={"check_same_thread": False},
    )
else:
    _ssl_args = {}
    if settings.APP_ENV == "production":
        _ssl_args = {"ssl": "require"}

    async_engine = create_async_engine(
        _async_url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        connect_args=_ssl_args,
    )

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_db() -> AsyncSession:  # type: ignore[return]
    """Async dependency that yields an AsyncSession."""
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Sync engine — kept for test fixtures, Alembic migrations, and legacy code
# ---------------------------------------------------------------------------

if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Shared declarative base (all models inherit from this)
Base = declarative_base()


def get_db():
    """Sync dependency — used by legacy routes and test fixtures."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize all tables using the sync engine (used in tests/startup)."""
    Base.metadata.create_all(bind=engine)
