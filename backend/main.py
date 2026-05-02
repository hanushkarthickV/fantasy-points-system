"""
FastAPI application entry point for the Fantasy Points System.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.logger import setup_logging, get_logger

# ── Logging (must be called before any other imports that use get_logger) ─────
setup_logging()

from backend.api.routes import router
from backend.api.routes_v2 import router_v2
from backend.api.auth import router_auth

logger = get_logger(__name__)


# ── Lifespan: create tables ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        from backend.db.base import engine, Base
        from backend.db import models  # noqa: F401 — registers models
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")

        # Start the background extraction worker
        from backend.services.extraction_worker import start_worker
        start_worker()
    else:
        logger.warning("DATABASE_URL not set — V2 features disabled")

    yield

    # Shutdown
    if db_url:
        from backend.services.extraction_worker import stop_worker
        stop_worker()


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fantasy Points System",
    description="Automated T20 fantasy-points calculator with ESPNcricinfo scraping",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)      # V1 routes (backwards compatible)
app.include_router(router_v2)   # V2 routes (match listing, extraction)
app.include_router(router_auth) # Auth routes


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ── Serve frontend build (production) ─────────────────────────────────────────
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    logger.info("Serving frontend static files from %s", FRONTEND_DIST)

    # Serve static assets (JS, CSS, images) under /assets/
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    # Catch-all: serve index.html for SPA client-side routing
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
