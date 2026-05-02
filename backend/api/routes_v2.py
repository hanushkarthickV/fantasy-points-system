"""
V2 API Routes — Match listing, queued extraction, points review, sheet update.

Endpoints:
  GET   /api/v2/matches                     → list all matches
  GET   /api/v2/matches/{id}/points         → get calculated points
  GET   /api/v2/matches/{id}/sheet-result   → get last sheet update result
  POST  /api/v2/matches/{id}/queue-extract  → add to extraction queue
  POST  /api/v2/matches/{id}/update-sheet   → push to sheet (returns results)
  PATCH /api/v2/matches/{id}/edit-players   → edit player names/points
  POST  /api/v2/sync-matches               → manually trigger match discovery
  GET   /api/v2/queue/status                → extraction queue status
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.base import get_db
from backend.db.models import (
    ExtractionQueue,
    Match,
    MatchStatus,
    QueueStatus,
)
from backend.logger import get_logger
from backend.models.schemas import (
    EditPlayersRequest,
    MatchPoints,
    SheetUpdateResponse,
)
from backend.services.sheet_service import SheetService

logger = get_logger(__name__)
router_v2 = APIRouter(prefix="/api/v2")

_sheet_service = SheetService()


# ── Pydantic response models ────────────────────────────────────────────────

class MatchListItem(BaseModel):
    id: int
    espn_match_id: str
    match_number: int | None
    title: str | None
    team1: str | None
    team2: str | None
    venue: str | None
    match_date: datetime | None
    status: str
    result_text: str | None
    scorecard_url: str | None
    extracted_at: datetime | None

    class Config:
        from_attributes = True


class MatchListResponse(BaseModel):
    matches: list[MatchListItem]
    total: int


class QueueItem(BaseModel):
    id: int
    match_id: int
    status: str
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


# ── Match Listing ─────────────────────────────────────────────────────────────

@router_v2.get("/matches", response_model=MatchListResponse)
async def list_matches(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all discovered matches with optional status filter."""
    q = db.query(Match).order_by(Match.match_number.desc().nullslast())
    if status:
        q = q.filter(Match.status == status)
    total = q.count()
    matches = q.offset(offset).limit(limit).all()
    return MatchListResponse(
        matches=[MatchListItem.model_validate(m) for m in matches],
        total=total,
    )


# ── Queue-based Extraction ──────────────────────────────────────────────────

@router_v2.post("/matches/{match_id}/queue-extract")
async def queue_extraction(match_id: int, db: Session = Depends(get_db)):
    """Add a match to the extraction queue. Returns immediately."""
    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")
    if not match.scorecard_url:
        raise HTTPException(422, "No scorecard URL available for this match")

    # Don't allow if already queued or extracting
    if match.status in (MatchStatus.QUEUED.value, MatchStatus.EXTRACTING.value):
        raise HTTPException(409, "Extraction already queued or in progress")

    # Check if already pending in queue
    existing = (
        db.query(ExtractionQueue)
        .filter(
            ExtractionQueue.match_id == match_id,
            ExtractionQueue.status.in_([QueueStatus.PENDING.value, QueueStatus.PROCESSING.value]),
        )
        .first()
    )
    if existing:
        raise HTTPException(409, "Extraction already in queue")

    # Add to queue and mark match as queued
    job = ExtractionQueue(match_id=match_id)
    db.add(job)
    match.status = MatchStatus.QUEUED.value
    db.commit()

    logger.info("[API] Match #%s (id=%d) queued for extraction", match.match_number, match_id)
    return {"message": "Extraction queued", "queue_id": job.id}


@router_v2.get("/queue/status")
async def queue_status(db: Session = Depends(get_db)):
    """Return current extraction queue status."""
    pending = db.query(ExtractionQueue).filter(ExtractionQueue.status == QueueStatus.PENDING.value).count()
    processing = db.query(ExtractionQueue).filter(ExtractionQueue.status == QueueStatus.PROCESSING.value).first()
    return {
        "pending_count": pending,
        "currently_processing": QueueItem.model_validate(processing).model_dump() if processing else None,
    }


# ── Points ────────────────────────────────────────────────────────────────────

@router_v2.get("/matches/{match_id}/points")
async def get_match_points(match_id: int, db: Session = Depends(get_db)):
    """Return the calculated points for a match."""
    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")
    if not match.points_json:
        raise HTTPException(422, "Points not yet calculated")
    return match.points_json


# ── Sheet Update ──────────────────────────────────────────────────────────────

@router_v2.post("/matches/{match_id}/update-sheet")
async def update_sheet_v2(match_id: int, db: Session = Depends(get_db)):
    """Push calculated points to Google Sheets. Returns matched/unmatched results."""
    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")
    if not match.points_json:
        raise HTTPException(422, "Points not yet calculated")

    points = MatchPoints(**match.points_json)
    result = _sheet_service.update_points_from_match(points)

    # Store the result and update status
    match.sheet_update_json = result.model_dump()
    match.status = MatchStatus.SHEET_UPDATED.value
    db.commit()

    return result.model_dump()


@router_v2.get("/matches/{match_id}/sheet-result")
async def get_sheet_result(match_id: int, db: Session = Depends(get_db)):
    """Return the stored sheet update result for a match."""
    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")
    if not match.sheet_update_json:
        raise HTTPException(422, "Sheet not yet updated for this match")
    return match.sheet_update_json


# ── Edit Players ──────────────────────────────────────────────────────────────

@router_v2.patch("/matches/{match_id}/edit-players")
async def edit_players_v2(match_id: int, request: EditPlayersRequest, db: Session = Depends(get_db)):
    """Edit player names/points in the stored points JSON."""
    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")
    if not match.points_json:
        raise HTTPException(422, "Points not yet calculated")

    points = MatchPoints(**match.points_json)
    player_map = {p.name: p for p in points.players}

    for edit in request.edits:
        player = player_map.get(edit.original_name)
        if not player:
            continue
        if edit.new_name and edit.new_name != edit.original_name:
            del player_map[edit.original_name]
            if edit.new_name in player_map:
                # Merge
                existing = player_map[edit.new_name]
                base_points = player.total_points - player.playing_xi_bonus
                existing.total_points += base_points
                if player.fielding:
                    if existing.fielding:
                        existing.fielding.catch_points += player.fielding.catch_points
                        existing.fielding.catch_bonus += player.fielding.catch_bonus
                        existing.fielding.stumping_points += player.fielding.stumping_points
                        existing.fielding.run_out_points += player.fielding.run_out_points
                        existing.fielding.total += player.fielding.total
                    else:
                        existing.fielding = player.fielding
                if player.batting:
                    if not existing.batting:
                        existing.batting = player.batting
                if player.bowling:
                    if not existing.bowling:
                        existing.bowling = player.bowling
            else:
                player.name = edit.new_name
                player_map[edit.new_name] = player
        if edit.new_total_points is not None:
            target = player_map.get(edit.new_name or edit.original_name)
            if target:
                target.total_points = edit.new_total_points

    points.players = list(player_map.values())
    match.points_json = points.model_dump()
    # Reset to points_calculated so user can update sheet again
    if match.status == MatchStatus.SHEET_UPDATED.value:
        match.status = MatchStatus.POINTS_CALCULATED.value
        match.sheet_update_json = None
    db.commit()

    return points.model_dump()


# ── Match Discovery (manual only) ────────────────────────────────────────────

@router_v2.post("/sync-matches")
async def sync_matches():
    """Manually trigger match discovery from ESPN schedule page."""
    from backend.scheduler.match_discovery import discover_matches
    try:
        new_count = discover_matches()
        return {"message": f"Discovery complete — {new_count} new matches", "new_matches": new_count}
    except Exception as e:
        raise HTTPException(500, f"Discovery failed: {str(e)[:200]}")
