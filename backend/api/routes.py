"""
FastAPI route definitions for the Fantasy Points System.

Each endpoint corresponds to one step of the human-in-the-loop workflow:
  1. POST /api/scrape          → scrape scorecard
  2. POST /api/calculate-points → calculate fantasy points
  3. POST /api/update-sheet     → push points to Google Sheets
  4. GET  /api/match/{id}/metadata
  5. GET  /api/match/{id}/points
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.logger import get_logger
from backend.models.schemas import (
    CalculatePointsRequest,
    MatchMetadata,
    MatchPoints,
    ScrapeRequest,
    SheetUpdateResponse,
    UpdateSheetRequest,
)
from backend.services.match_service import MatchService

logger = get_logger(__name__)
router = APIRouter(prefix="/api")

# Single service instance shared across requests
_match_service = MatchService()


# ── Step 1: Scrape ─────────────────────────────────────────────────────────────

@router.post("/scrape", response_model=MatchMetadata)
async def scrape_scorecard(request: ScrapeRequest):
    """Scrape the scorecard at the given URL and return match metadata."""
    logger.info("[SCRAPE] Received request for URL: %s", request.url)
    try:
        metadata = _match_service.scrape_match(request.url)
        logger.info("[SCRAPE] Success — match_id=%s, title=%s, innings=%d", metadata.match_id, metadata.match_title, len(metadata.innings))
        return metadata
    except Exception as exc:
        logger.exception("[SCRAPE] FAILED for URL: %s", request.url)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Step 2: Calculate Points ───────────────────────────────────────────────────

@router.post("/calculate-points", response_model=MatchPoints)
async def calculate_points(request: CalculatePointsRequest):
    """Calculate fantasy points for a previously scraped match."""
    logger.info("[POINTS] Received request for match_id=%s", request.match_id)
    try:
        points = _match_service.calculate_points(request.match_id)
        logger.info("[POINTS] Success — %d players scored", len(points.players))
        return points
    except FileNotFoundError as exc:
        logger.warning("[POINTS] Metadata not found for match_id=%s", request.match_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[POINTS] FAILED for match_id=%s", request.match_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Step 3: Update Sheet ──────────────────────────────────────────────────────

@router.post("/update-sheet", response_model=SheetUpdateResponse)
async def update_sheet(request: UpdateSheetRequest):
    """Push calculated points to Google Sheets and return before/after diff."""
    logger.info("[SHEET] Received update request for match_id=%s", request.match_id)
    try:
        result = _match_service.update_sheet(request.match_id)
        logger.info("[SHEET] Success — %d updated, %d unmatched", len(result.updated_players), len(result.unmatched_players))
        return result
    except FileNotFoundError as exc:
        logger.warning("[SHEET] Points not found for match_id=%s", request.match_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[SHEET] FAILED for match_id=%s", request.match_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Read-only endpoints ────────────────────────────────────────────────────────

@router.get("/match/{match_id}/metadata", response_model=MatchMetadata)
async def get_metadata(match_id: str):
    """Return the saved metadata for a match."""
    try:
        return _match_service.get_metadata(match_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/match/{match_id}/points", response_model=MatchPoints)
async def get_points(match_id: str):
    """Return the saved points for a match."""
    try:
        return _match_service.get_points(match_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
