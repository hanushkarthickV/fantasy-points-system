"""
FastAPI application entry point for the Fantasy Points System.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.logger import setup_logging, get_logger

# ── Logging (must be called before any other imports that use get_logger) ─────
setup_logging()

from backend.api.routes import router

logger = get_logger(__name__)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fantasy Points System",
    description="Automated T20 fantasy-points calculator with ESPNcricinfo scraping",
    version="1.0.0",
)

# CORS — allow the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}


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
