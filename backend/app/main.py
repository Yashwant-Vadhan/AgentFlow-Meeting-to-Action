"""
FastAPI application entrypoint.

Boots the app with:
- CORS middleware (allow frontend origin)
- Lifespan handler for DB init
- API route includes
- Health check endpoint
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.schema import Base

# ── Logging setup ─────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Database engine (module-level, created at import) ─
settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Dependency — yields an async DB session."""
    async with async_session() as session:
        yield session


# ── Lifespan (startup / shutdown) ─────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup, dispose engine on shutdown."""
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")

    # Ensure upload directory exists
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload directory: {upload_dir.resolve()}")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("Database engine disposed")


# ── App factory ───────────────────────────────
app = FastAPI(
    title="AgentFlow: Meeting-to-Action",
    description="Agentic AI pipeline for automated meeting-to-action extraction",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server and any localhost origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check ──────────────────────────────
@app.get("/health", tags=["system"])
async def health_check():
    """Basic health check — confirms the backend is running."""
    return {
        "status": "healthy",
        "service": "meeting-to-action-backend",
        "ollama_model": settings.ollama_model,
    }


# ── Route includes ────────────────────────────
# Import and include API routers here as they are built.
# These are added after the routers are implemented to avoid
# import errors on empty files.

def _include_routers():
    """Include API routers. Called after app creation."""
    try:
        from app.api.sessions import router as sessions_router
        app.include_router(sessions_router, prefix="/api/v1", tags=["sessions"])
        logger.info("Sessions router included")
    except (ImportError, Exception) as e:
        logger.warning(f"Sessions router not loaded: {e}")

    try:
        from app.api.websocket import router as ws_router
        app.include_router(ws_router, tags=["websocket"])
        logger.info("WebSocket router included")
    except (ImportError, Exception) as e:
        logger.warning(f"WebSocket router not loaded: {e}")


_include_routers()
