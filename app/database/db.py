"""
app/database/db.py
==================
SQLAlchemy database session factory and lifecycle management.

Design decisions:
  - Uses SQLAlchemy 2.x async engine with aiosqlite for non-blocking I/O.
  - Session lifecycle is managed via a FastAPI dependency (`get_db`) using
    async context management — sessions are always closed after the request.
  - `init_db()` is called once at application startup to create all tables;
    it is idempotent and safe to call multiple times.
  - The engine is a module-level singleton; session factories are lightweight.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings, get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────
# ORM Base — all models inherit from this
# ─────────────────────────────────────────────

class Base(DeclarativeBase):
    """
    Declarative ORM base class.

    All SQLAlchemy models in ``app/database/models.py`` must inherit from this
    class so that ``Base.metadata.create_all()`` discovers them automatically.
    """
    pass


# ─────────────────────────────────────────────
# Engine & Session Factory
# ─────────────────────────────────────────────

def _build_engine(settings: Settings) -> AsyncEngine:
    """
    Construct the SQLAlchemy async engine from application settings.

    The ``check_same_thread=False`` connect arg is required for SQLite when
    used with async drivers (multiple coroutines on different threads).
    """
    db_url = settings.database_url

    # Convert synchronous sqlite:/// URL to async aiosqlite:///
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

    logger.info("Initialising database engine", extra={"url": db_url})

    return create_async_engine(
        db_url,
        echo=settings.sqlalchemy_echo,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,  # Detect stale connections before use
    )


def _build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Prevent lazy-load errors post-commit
        autoflush=False,
        autocommit=False,
    )


# Module-level singletons — initialised lazily at first access
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return (or lazily create) the shared async engine."""
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings())
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return (or lazily create) the shared session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = _build_session_factory(get_engine())
    return _session_factory


# ─────────────────────────────────────────────
# FastAPI Dependency
# ─────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.

    The session is automatically committed on success and rolled back on
    exception, then closed regardless of outcome.

    Usage::
        from app.database.db import get_db, DBSession

        @router.post("/submit")
        async def submit(db: DBSession):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Annotated type alias for cleaner route signatures
DBSession = Annotated[AsyncSession, Depends(get_db)]


# ─────────────────────────────────────────────
# Startup / Shutdown Hooks
# ─────────────────────────────────────────────

async def init_db() -> None:
    """
    Create all database tables defined in the ORM models.

    Called once during application startup (``app/main.py`` lifespan).
    This is idempotent — existing tables are never dropped or modified.
    """
    # Import models here to ensure they are registered with Base.metadata
    from app.database import models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables initialised successfully.")


async def close_db() -> None:
    """
    Dispose the engine connection pool.

    Called during application shutdown (``app/main.py`` lifespan).
    """
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database engine disposed.")
        _engine = None
