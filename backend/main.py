"""
FastAPI application entry point for the Fantasy Points System.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
