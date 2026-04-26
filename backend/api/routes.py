"""
FastAPI route definitions for the Fantasy Points System.

Each endpoint corresponds to one step of the human-in-the-loop workflow:
  1. POST /api/scrape              → scrape scorecard
  2. POST /api/calculate-points    → calculate fantasy points
  3. POST /api/update-sheet        → push points to Google Sheets
  4. PATCH /api/edit-players       → edit player names/points before sheet push
  5. POST /api/retry-unmatched     → retry unmatched players with corrected names
  6. GET  /api/match/{id}/metadata
  7. GET  /api/match/{id}/points
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from backend.logger import get_logger
from backend.models.schemas import (
    CalculatePointsRequest,
    EditPlayersRequest,
    MatchMetadata,
    MatchPoints,
    RetryUnmatchedRequest,
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
    except ValueError as exc:
        logger.warning("[SCRAPE] Validation error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TimeoutError as exc:
        logger.warning("[SCRAPE] Timeout scraping URL: %s", request.url)
        raise HTTPException(
            status_code=504,
            detail="The page took too long to load. Please check the URL and try again.",
        ) from exc
    except Exception as exc:
        error_msg = str(exc)
        if "timeout" in error_msg.lower() or "Timed out" in error_msg:
            logger.warning("[SCRAPE] Timeout for URL: %s", request.url)
            raise HTTPException(
                status_code=504,
                detail="The page took too long to load. Please verify the URL is a valid ESPNcricinfo scorecard.",
            ) from exc
        logger.exception("[SCRAPE] FAILED for URL: %s", request.url)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to scrape scorecard: {error_msg[:200]}",
        ) from exc


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
        raise HTTPException(status_code=500, detail=f"Points calculation failed: {str(exc)[:200]}") from exc


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
        raise HTTPException(status_code=500, detail=f"Sheet update failed: {str(exc)[:200]}") from exc


# ── Step 4: Edit Players (before sheet push) ─────────────────────────────────

@router.patch("/edit-players", response_model=MatchPoints)
async def edit_players(request: EditPlayersRequest):
    """Edit player names or total_points in the saved points JSON."""
    logger.info("[EDIT] Editing %d player(s) for match_id=%s", len(request.edits), request.match_id)
    try:
        updated = _match_service.edit_players(request.match_id, request.edits)
        logger.info("[EDIT] Success — updated points saved")
        return updated
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[EDIT] FAILED for match_id=%s", request.match_id)
        raise HTTPException(status_code=500, detail=f"Edit failed: {str(exc)[:200]}") from exc


# ── Step 5: Retry Unmatched Players ──────────────────────────────────────────

@router.post("/retry-unmatched", response_model=SheetUpdateResponse)
async def retry_unmatched(request: RetryUnmatchedRequest):
    """Retry updating sheet for unmatched players with corrected names."""
    logger.info("[RETRY] Retrying %d unmatched player(s) for match_id=%s", len(request.name_corrections), request.match_id)
    try:
        result = _match_service.retry_unmatched(request.match_id, request.name_corrections)
        logger.info("[RETRY] Success — %d updated", len(result.updated_players))
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[RETRY] FAILED for match_id=%s", request.match_id)
        raise HTTPException(status_code=500, detail=f"Retry failed: {str(exc)[:200]}") from exc


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
