"""
V2 API Routes — Match listing, extraction, scheduler control, auth.

Endpoints:
  GET  /api/v2/matches                  → list all matches
  POST /api/v2/matches/{id}/extract     → trigger extraction for a match
  GET  /api/v2/matches/{id}/extract-stream → SSE extraction progress
  POST /api/v2/matches/{id}/calculate   → calculate points
  POST /api/v2/matches/{id}/update-sheet → push to sheet
  PATCH /api/v2/matches/{id}/edit-players → edit players
  POST /api/v2/scheduler/run            → manually trigger discovery
  GET  /api/v2/scheduler/status         → scheduler health
  POST /api/v2/auth/signup              → register
  POST /api/v2/auth/login               → login
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.base import get_db
from backend.db.models import Extraction, Match, MatchStatus
from backend.engine.points_calculator import calculate_match_points
from backend.logger import get_logger
from backend.models.schemas import (
    EditPlayersRequest,
    MatchMetadata,
    MatchPoints,
    PlayerEdit,
    SheetUpdateResponse,
)
from backend.scraper.scorecard_scraper import scrape_scorecard
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


class ExtractionResponse(BaseModel):
    message: str
    status: str


class SchedulerStatusResponse(BaseModel):
    running: bool
    last_run: str | None
    next_run: str | None


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


# ── Extraction ────────────────────────────────────────────────────────────────

@router_v2.post("/matches/{match_id}/extract", response_model=ExtractionResponse)
async def trigger_extraction(match_id: int, db: Session = Depends(get_db)):
    """Trigger scorecard extraction for a match (non-streaming, synchronous)."""
    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")
    if match.status == MatchStatus.EXTRACTING:
        raise HTTPException(409, "Extraction already in progress")
    if not match.scorecard_url:
        raise HTTPException(422, "No scorecard URL available for this match")

    # Lock the match
    match.status = MatchStatus.EXTRACTING
    db.commit()

    # Create extraction record
    extraction = Extraction(espn_match_id=match.espn_match_id, status="in_progress")
    db.add(extraction)
    db.commit()

    try:
        metadata = scrape_scorecard(match.scorecard_url)
        match.metadata_json = metadata.model_dump()
        match.status = MatchStatus.EXTRACTED
        match.extracted_at = datetime.utcnow()
        match.team1 = metadata.team1
        match.team2 = metadata.team2
        match.title = metadata.match_title
        extraction.status = "success"
        extraction.completed_at = datetime.utcnow()
        db.commit()
        return ExtractionResponse(message="Extraction successful", status="extracted")
    except Exception as e:
        match.status = MatchStatus.EXTRACTION_FAILED
        extraction.status = "failed"
        extraction.error_message = str(e)[:500]
        extraction.completed_at = datetime.utcnow()
        db.commit()
        logger.exception("[EXTRACT] Failed for match %d", match_id)
        raise HTTPException(500, f"Extraction failed: {str(e)[:200]}")


@router_v2.get("/matches/{match_id}/extract-stream")
async def extract_stream(match_id: int, db: Session = Depends(get_db)):
    """SSE stream for real-time extraction progress."""
    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")
    if not match.scorecard_url:
        raise HTTPException(422, "No scorecard URL available")
    if match.status == MatchStatus.EXTRACTING:
        raise HTTPException(409, "Extraction already in progress")

    # Lock the match
    match.status = MatchStatus.EXTRACTING
    db.commit()

    extraction = Extraction(espn_match_id=match.espn_match_id, status="in_progress")
    db.add(extraction)
    db.commit()
    extraction_id = extraction.id

    progress_q: queue.Queue = queue.Queue()

    def on_progress(step: str, message: str):
        progress_q.put(("progress", step, message))

    def run_scraper():
        db_inner = None
        try:
            from backend.db.base import SessionLocal
            db_inner = SessionLocal()
            metadata = scrape_scorecard(match.scorecard_url, on_progress=on_progress)

            m = db_inner.query(Match).filter_by(id=match_id).first()
            m.metadata_json = metadata.model_dump()
            m.status = MatchStatus.EXTRACTED
            m.extracted_at = datetime.utcnow()
            m.team1 = metadata.team1
            m.team2 = metadata.team2
            m.title = metadata.match_title

            ext = db_inner.query(Extraction).filter_by(id=extraction_id).first()
            ext.status = "success"
            ext.completed_at = datetime.utcnow()
            db_inner.commit()

            progress_q.put(("done", metadata.model_dump(), None))
        except Exception as e:
            if db_inner:
                m = db_inner.query(Match).filter_by(id=match_id).first()
                if m:
                    m.status = MatchStatus.EXTRACTION_FAILED
                ext = db_inner.query(Extraction).filter_by(id=extraction_id).first()
                if ext:
                    ext.status = "failed"
                    ext.error_message = str(e)[:500]
                    ext.completed_at = datetime.utcnow()
                db_inner.commit()
            progress_q.put(("error", f"Extraction failed: {str(e)[:200]}", None))
        finally:
            if db_inner:
                db_inner.close()

    thread = threading.Thread(target=run_scraper, daemon=True)
    thread.start()

    _PAD = " " * 2048

    async def event_generator():
        yield f": {_PAD}\n: stream-start\n\n"
        while True:
            try:
                item = progress_q.get_nowait()
            except queue.Empty:
                if not thread.is_alive() and progress_q.empty():
                    break
                yield f": keepalive{_PAD}\n\n"
                await asyncio.sleep(0.4)
                continue

            kind = item[0]
            if kind == "progress":
                _, step, message = item
                yield f"event: progress\ndata: {json.dumps({'step': step, 'message': message})}\n\n"
            elif kind == "done":
                _, data, _ = item
                yield f"event: done\ndata: {json.dumps(data)}\n\n"
                break
            elif kind == "error":
                _, message, _ = item
                yield f"event: error\ndata: {json.dumps({'message': message})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── Points Calculation ────────────────────────────────────────────────────────

@router_v2.post("/matches/{match_id}/calculate")
async def calculate_points_v2(match_id: int, db: Session = Depends(get_db)):
    """Calculate fantasy points for an extracted match."""
    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")
    if not match.metadata_json:
        raise HTTPException(422, "Match not yet extracted")

    metadata = MatchMetadata(**match.metadata_json)

    try:
        bowler_names = _sheet_service.get_bowler_names()
    except Exception:
        bowler_names = set()

    points = calculate_match_points(metadata, bowler_names)
    match.points_json = points.model_dump()
    match.status = MatchStatus.POINTS_CALCULATED
    db.commit()

    return points.model_dump()


# ── Sheet Update ──────────────────────────────────────────────────────────────

@router_v2.post("/matches/{match_id}/update-sheet")
async def update_sheet_v2(match_id: int, db: Session = Depends(get_db)):
    """Push calculated points to Google Sheets."""
    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")
    if not match.points_json:
        raise HTTPException(422, "Points not yet calculated")

    points = MatchPoints(**match.points_json)
    result = _sheet_service.update_points_from_match(points)
    match.status = MatchStatus.SHEET_UPDATED
    db.commit()

    return result.model_dump()


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
    db.commit()

    return points.model_dump()


# ── Scheduler Control ─────────────────────────────────────────────────────────

@router_v2.post("/scheduler/run")
async def run_scheduler_now():
    """Manually trigger match discovery."""
    from backend.scheduler.scheduler import run_discovery_now
    try:
        new_count = run_discovery_now()
        return {"message": f"Discovery complete — {new_count} new matches", "new_matches": new_count}
    except Exception as e:
        raise HTTPException(500, f"Discovery failed: {str(e)[:200]}")


@router_v2.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def scheduler_status():
    """Return scheduler health info."""
    from backend.scheduler.scheduler import _scheduler
    if not _scheduler or not _scheduler.running:
        return SchedulerStatusResponse(running=False, last_run=None, next_run=None)

    job = _scheduler.get_job("match_discovery")
    next_run = str(job.next_run_time) if job and job.next_run_time else None
    return SchedulerStatusResponse(running=True, last_run=None, next_run=next_run)
