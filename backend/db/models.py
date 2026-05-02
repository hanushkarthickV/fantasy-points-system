"""
SQLAlchemy ORM models for the Fantasy Points System V2.

Tables:
  - matches: One row per IPL match discovered from the schedule
  - extractions: Tracks each extraction attempt for a match
  - users: Authentication (email + hashed password or OTP)
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    func,
)

from backend.db.base import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"            # match found but not yet played
    COMPLETED = "completed"            # match played, ready for extraction
    QUEUED = "queued"                  # extraction queued
    EXTRACTING = "extracting"          # extraction in progress
    POINTS_CALCULATED = "points_calculated"  # extracted + points ready
    SHEET_UPDATED = "sheet_updated"    # pushed to Google Sheets
    EXTRACTION_FAILED = "extraction_failed"
    MANUALLY_EXTRACTED = "manually_extracted"  # matches 1-42


# ── Match ─────────────────────────────────────────────────────────────────────

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    espn_match_id = Column(String(32), unique=True, nullable=False, index=True)
    match_number = Column(Integer, nullable=True)
    title = Column(String(256), nullable=True)
    team1 = Column(String(128), nullable=True)
    team2 = Column(String(128), nullable=True)
    venue = Column(String(256), nullable=True)
    match_date = Column(DateTime, nullable=True)
    scorecard_url = Column(Text, nullable=True)
    status = Column(
        String(32),
        nullable=False,
        default=MatchStatus.SCHEDULED.value,
        server_default="scheduled",
    )
    result_text = Column(Text, nullable=True)
    # JSON blob of full metadata (MatchMetadata dict) after extraction
    metadata_json = Column(JSON, nullable=True)
    # JSON blob of calculated points (MatchPoints dict)
    points_json = Column(JSON, nullable=True)
    # JSON blob of last sheet update result (SheetUpdateResponse dict)
    sheet_update_json = Column(JSON, nullable=True)
    # Timestamps
    discovered_at = Column(DateTime, server_default=func.now(), nullable=False)
    extracted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Match #{self.match_number} ({self.espn_match_id}) status={self.status}>"


# ── Extraction (audit log) ────────────────────────────────────────────────────

class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    espn_match_id = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="in_progress")  # in_progress, success, failed
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Extraction match={self.espn_match_id} status={self.status}>"


# ── Extraction Queue (async job queue) ───────────────────────────────

class QueueStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ExtractionQueue(Base):
    __tablename__ = "extraction_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, nullable=False, index=True)
    status = Column(String(32), nullable=False, default=QueueStatus.PENDING.value, server_default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ExtractionQueue match_id={self.match_id} status={self.status}>"


# ── App Config (persistent key-value store) ──────────────────────────────────

class AppConfig(Base):
    __tablename__ = "app_config"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<AppConfig {self.key}={self.value}>"


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.email}>"
