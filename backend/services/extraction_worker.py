"""
Background extraction worker — processes the extraction_queue table one job at a time.

This replaces the old APScheduler approach. The worker runs in a daemon thread,
polling the queue every 3 seconds for pending jobs. Each job:
  1. Scrapes the scorecard (Selenium)
  2. Calculates fantasy points
  3. Stores results in the match row
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from backend.logger import get_logger

logger = get_logger(__name__)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _process_one_job() -> bool:
    """Pick the oldest PENDING job, process it. Returns True if a job was found."""
    from backend.db.base import SessionLocal
    from backend.db.models import ExtractionQueue, Match, MatchStatus, QueueStatus, Extraction
    from backend.scraper.scorecard_scraper import scrape_scorecard
    from backend.engine.points_calculator import calculate_match_points
    from backend.models.schemas import MatchMetadata
    from backend.services.sheet_service import SheetService

    db = SessionLocal()
    try:
        # Grab oldest pending job
        job = (
            db.query(ExtractionQueue)
            .filter(ExtractionQueue.status == QueueStatus.PENDING.value)
            .order_by(ExtractionQueue.created_at.asc())
            .first()
        )
        if not job:
            return False

        match = db.query(Match).filter_by(id=job.match_id).first()
        if not match or not match.scorecard_url:
            job.status = QueueStatus.FAILED.value
            job.error_message = "Match not found or no scorecard URL"
            job.completed_at = datetime.utcnow()
            if match:
                match.status = MatchStatus.EXTRACTION_FAILED.value
            db.commit()
            return True

        # Mark processing
        job.status = QueueStatus.PROCESSING.value
        job.started_at = datetime.utcnow()
        match.status = MatchStatus.EXTRACTING.value
        db.commit()

        logger.info("[WORKER] Processing extraction for match #%s (id=%d)", match.match_number, match.id)

        # Create audit extraction record
        extraction = Extraction(espn_match_id=match.espn_match_id, status="in_progress")
        db.add(extraction)
        db.commit()

        try:
            # Step 1: Scrape
            metadata = scrape_scorecard(match.scorecard_url)
            match.metadata_json = metadata.model_dump()
            match.extracted_at = datetime.utcnow()
            match.team1 = metadata.team1
            match.team2 = metadata.team2
            match.title = metadata.match_title
            if metadata.venue:
                match.venue = metadata.venue
            if metadata.date:
                try:
                    from dateutil.parser import parse as parse_date
                    match.match_date = parse_date(metadata.date)
                except Exception:
                    pass  # best-effort date parsing
            extraction.status = "success"
            extraction.completed_at = datetime.utcnow()

            # Step 2: Calculate points automatically
            try:
                sheet_svc = SheetService()
                bowler_names = sheet_svc.get_bowler_names()
            except Exception:
                bowler_names = set()

            points = calculate_match_points(metadata, bowler_names)
            match.points_json = points.model_dump()

            # If match was previously manually_extracted / sheet_updated,
            # skip the review step and go straight to sheet_updated (read-only history).
            if job.skip_review:
                match.status = MatchStatus.SHEET_UPDATED.value
                logger.info("[WORKER] skip_review=True → status set to sheet_updated for match #%s", match.match_number)
            else:
                match.status = MatchStatus.POINTS_CALCULATED.value

            # Mark job done
            job.status = QueueStatus.DONE.value
            job.completed_at = datetime.utcnow()
            db.commit()

            logger.info("[WORKER] Extraction + points complete for match #%s", match.match_number)

        except Exception as e:
            match.status = MatchStatus.EXTRACTION_FAILED.value
            extraction.status = "failed"
            extraction.error_message = str(e)[:500]
            extraction.completed_at = datetime.utcnow()
            job.status = QueueStatus.FAILED.value
            job.error_message = str(e)[:500]
            job.completed_at = datetime.utcnow()
            db.commit()
            logger.exception("[WORKER] Extraction failed for match #%s", match.match_number)

        return True

    except Exception:
        logger.exception("[WORKER] Unexpected error in worker loop")
        return False
    finally:
        db.close()


def _worker_loop():
    """Main worker loop — polls queue every 3 seconds."""
    logger.info("[WORKER] Extraction worker started")
    while not _stop_event.is_set():
        try:
            had_work = _process_one_job()
            if not had_work:
                # No jobs — sleep before next poll
                _stop_event.wait(timeout=3)
        except Exception:
            logger.exception("[WORKER] Error in worker loop")
            _stop_event.wait(timeout=5)
    logger.info("[WORKER] Extraction worker stopped")


def start_worker():
    """Start the background extraction worker thread."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="extraction-worker")
    _worker_thread.start()


def stop_worker():
    """Stop the background extraction worker."""
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=10)
