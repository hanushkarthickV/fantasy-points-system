from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel, field_validator


# ── URL validation pattern ─────────────────────────────────────────────────────

_ESPNCRICINFO_PATTERN = re.compile(
    r"https?://(?:www\.)?espncricinfo\.com/.+/full-scorecard"
)


# ── Scraping Input / Output ────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_espncricinfo_url(cls, v: str) -> str:
        v = v.strip()
        if not _ESPNCRICINFO_PATTERN.match(v):
            raise ValueError(
                "URL must be a valid ESPNcricinfo full-scorecard URL "
                "(e.g. https://www.espncricinfo.com/series/.../full-scorecard)"
            )
        return v


class CalculatePointsRequest(BaseModel):
    match_id: str


class UpdateSheetRequest(BaseModel):
    match_id: str


# ── Player Performance Data ────────────────────────────────────────────────────

class BattingEntry(BaseModel):
    name: str
    dismissal: str          # e.g. "c Klaasen b Malinga", "not out", "lbw b X"
    runs: int
    balls: int
    minutes: int
    fours: int
    sixes: int
    strike_rate: float
    is_not_out: bool = False


class BowlingEntry(BaseModel):
    name: str
    overs: float            # e.g. 3.3 means 3 overs 3 balls
    maidens: int
    runs_conceded: int
    wickets: int
    economy: float
    dot_balls: int
    wides: int
    no_balls: int


class FieldingEntry(BaseModel):
    name: str
    catches: int = 0
    stumpings: int = 0
    run_out_direct: int = 0
    run_out_indirect: int = 0


class DismissalDetail(BaseModel):
    batter_name: str
    dismissal_type: str     # "caught", "bowled", "lbw", "stumped", "run_out", "hit_wicket", "not_out"
    bowler_name: Optional[str] = None
    fielder_name: Optional[str] = None
    is_direct_run_out: bool = False
    is_keeper_catch: bool = False   # True when † indicates wicketkeeper took the catch


class InningsData(BaseModel):
    team_name: str
    batting: list[BattingEntry]
    bowling: list[BowlingEntry]
    fielding: list[FieldingEntry]
    did_not_bat: list[str]
    dismissals: list[DismissalDetail]
    wicketkeeper: Optional[str] = None  # Full name of the team's wicketkeeper
    extras: int = 0
    total_runs: int = 0
    total_wickets: int = 0
    total_overs: float = 0.0


class MatchMetadata(BaseModel):
    match_id: str
    match_title: str
    venue: str
    date: str
    team1: str
    team2: str
    result: str
    innings: list[InningsData]
    url: str


# ── Points Data ────────────────────────────────────────────────────────────────

class BattingPointsBreakdown(BaseModel):
    run_points: int = 0
    four_bonus: int = 0
    six_bonus: int = 0
    milestone_bonus: int = 0
    duck_penalty: int = 0
    strike_rate_bonus: int = 0
    total: int = 0


class BowlingPointsBreakdown(BaseModel):
    wicket_points: int = 0
    maiden_bonus: int = 0
    lbw_bowled_bonus: int = 0
    haul_bonus: int = 0
    dot_ball_points: int = 0
    economy_bonus: int = 0
    total: int = 0


class FieldingPointsBreakdown(BaseModel):
    catch_points: int = 0
    catch_bonus: int = 0
    stumping_points: int = 0
    run_out_points: int = 0
    total: int = 0


class PlayerPoints(BaseModel):
    name: str
    team: str
    batting: Optional[BattingPointsBreakdown] = None
    bowling: Optional[BowlingPointsBreakdown] = None
    fielding: Optional[FieldingPointsBreakdown] = None
    playing_xi_bonus: int = 0
    total_points: int = 0


class MatchPoints(BaseModel):
    match_id: str
    players: list[PlayerPoints]


# ── Sheet Update ───────────────────────────────────────────────────────────────

class PlayerUpdateResult(BaseModel):
    scraped_name: str
    matched_name: str
    match_score: int
    previous_points: float
    added_points: int
    new_points: float
    specialism: str = ""


class SheetUpdateResponse(BaseModel):
    match_id: str
    updated_players: list[PlayerUpdateResult]
    unmatched_players: list[str]


# ── Player Edit / Retry Unmatched ─────────────────────────────────────────────

class PlayerEdit(BaseModel):
    original_name: str
    new_name: Optional[str] = None
    new_total_points: Optional[int] = None


class EditPlayersRequest(BaseModel):
    match_id: str
    edits: list[PlayerEdit]


class RetryUnmatchedRequest(BaseModel):
    match_id: str
    name_corrections: dict[str, str]  # {scraped_display_name: corrected_sheet_name}
