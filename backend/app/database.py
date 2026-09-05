"""
database.py — async SQLAlchemy engine + session factory.

Provides:
  • engine / AsyncSessionLocal for use throughout the app
  • init_db() — creates all tables on startup
  • get_db() — FastAPI dependency that yields a DB session per request
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.schema import Base

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite only
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables defined in schema.py (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """FastAPI dependency: yields one AsyncSession per request."""
    async with AsyncSessionLocal() as session:
        yield session
