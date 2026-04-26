"""
Pure-function T20 Fantasy Points calculator.

Every scoring rule from the T20 Point Scoring System is implemented here.
All functions are stateless and side-effect-free.
"""

from __future__ import annotations

import math

from backend.logger import get_logger
from backend.models.schemas import (
    BattingEntry,
    BattingPointsBreakdown,
    BowlingEntry,
    BowlingPointsBreakdown,
    DismissalDetail,
    FieldingEntry,
    FieldingPointsBreakdown,
    InningsData,
    MatchMetadata,
    MatchPoints,
    PlayerPoints,
)

logger = get_logger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────

def calculate_match_points(
    metadata: MatchMetadata,
    bowler_names: set[str] | None = None,
) -> MatchPoints:
    """
    Calculate fantasy points for every player in the match.

    *bowler_names* is an optional set of player names whose ``Specialism``
    is ``BOWLER`` — used to determine duck-penalty exemption.  If ``None``,
    no duck-penalty exemption is applied.
    """
    if bowler_names is None:
        bowler_names = set()

    player_map: dict[str, PlayerPoints] = {}
    logger.info("[CALC] Calculating points for match %s (%d innings)", metadata.match_id, len(metadata.innings))

    for innings in metadata.innings:
        batting_team = innings.team_name
        # The bowling/fielding side is the *other* team
        bowling_team = (
            metadata.team2 if batting_team == metadata.team1 else metadata.team1
        )

        # ── Batting points (for the batting team) ──────────────────────────
        for entry in innings.batting:
            pp = _get_or_create(player_map, entry.name, batting_team)
            pp.batting = calculate_batting_points(entry, bowler_names)
            pp.total_points += pp.batting.total

        # ── Bowling points (bowlers belong to the fielding team) ───────────
        for entry in innings.bowling:
            pp = _get_or_create(player_map, entry.name, bowling_team)
            # Gather lbw/bowled count for this bowler from dismissals
            lbw_bowled = _count_lbw_bowled(entry.name, innings.dismissals)
            pp.bowling = calculate_bowling_points(entry, lbw_bowled)
            pp.total_points += pp.bowling.total

        # ── Fielding points (fielders belong to the fielding team) ─────────
        for entry in innings.fielding:
            pp = _get_or_create(player_map, entry.name, bowling_team)
            pp.fielding = calculate_fielding_points(entry)
            pp.total_points += pp.fielding.total

    # ── Playing XI bonus: +4 for every player who featured ───────────────
    PLAYING_XI_BONUS = 4
    for pp in player_map.values():
        pp.playing_xi_bonus = PLAYING_XI_BONUS
        pp.total_points += PLAYING_XI_BONUS

    for pp in player_map.values():
        logger.debug("[CALC] %s (%s): bat=%s bowl=%s field=%s xi=%d total=%d",
                     pp.name, pp.team,
                     pp.batting.total if pp.batting else '-',
                     pp.bowling.total if pp.bowling else '-',
                     pp.fielding.total if pp.fielding else '-',
                     pp.playing_xi_bonus,
                     pp.total_points)

    logger.info("[CALC] Done — %d players scored (incl. +%d Playing XI bonus each)", len(player_map), PLAYING_XI_BONUS)
    return MatchPoints(
        match_id=metadata.match_id,
        players=list(player_map.values()),
    )


# ── Batting ────────────────────────────────────────────────────────────────────

def calculate_batting_points(
    entry: BattingEntry,
    bowler_names: set[str],
) -> BattingPointsBreakdown:
    """Calculate batting fantasy points for a single innings."""
    bp = BattingPointsBreakdown()

    # Runs: +1 per run
    bp.run_points = entry.runs * 1

    # Boundary bonuses
    bp.four_bonus = entry.fours * 4
    bp.six_bonus = entry.sixes * 6

    # Milestone bonuses (cumulative thresholds)
    bp.milestone_bonus = _milestone_bonus(entry.runs)

    # Duck penalty: -2 if dismissed for 0, excluding bowlers
    if (
        entry.runs == 0
        and not entry.is_not_out
        and entry.name not in bowler_names
    ):
        bp.duck_penalty = -2

    # Strike-rate bonus/penalty (min 20 runs scored OR 10 balls played)
    if entry.runs >= 20 or entry.balls >= 10:
        bp.strike_rate_bonus = _strike_rate_points(entry.strike_rate)

    bp.total = (
        bp.run_points
        + bp.four_bonus
        + bp.six_bonus
        + bp.milestone_bonus
        + bp.duck_penalty
        + bp.strike_rate_bonus
    )
    return bp


def _milestone_bonus(runs: int) -> int:
    """Cumulative milestone bonuses: 25→+4, 50→+8, 75→+12, 100→+16."""
    bonus = 0
    if runs >= 100:
        bonus += 16
    if runs >= 75:
        bonus += 12
    if runs >= 50:
        bonus += 8
    if runs >= 25:
        bonus += 4
    return bonus


def _strike_rate_points(sr: float) -> int:
    """Tiered strike-rate bonus/penalty."""
    if sr >= 170:
        return 6
    if sr >= 150:
        return 4
    if sr >= 130:
        return 2
    if sr >= 70:
        return 0
    if sr >= 60:
        return -2
    if sr >= 50:
        return -4
    return -6


# ── Bowling ────────────────────────────────────────────────────────────────────

def calculate_bowling_points(
    entry: BowlingEntry,
    lbw_bowled_count: int,
) -> BowlingPointsBreakdown:
    """Calculate bowling fantasy points for a single innings."""
    bp = BowlingPointsBreakdown()

    # Wickets: +30 each (run-outs excluded — they don't appear as bowler wickets)
    bp.wicket_points = entry.wickets * 30

    # Maiden overs: +12 each
    bp.maiden_bonus = entry.maidens * 12

    # LBW / Bowled bonus: +8 per such dismissal
    bp.lbw_bowled_bonus = lbw_bowled_count * 8

    # Wicket-haul bonuses (cumulative)
    bp.haul_bonus = _haul_bonus(entry.wickets)

    # Dot balls: +1 each
    bp.dot_ball_points = entry.dot_balls * 1

    # Economy-rate bonus/penalty (minimum 2 overs bowled)
    overs_bowled = _overs_to_balls(entry.overs) / 6
    if overs_bowled >= 2:
        bp.economy_bonus = _economy_rate_points(entry.economy)

    bp.total = (
        bp.wicket_points
        + bp.maiden_bonus
        + bp.lbw_bowled_bonus
        + bp.haul_bonus
        + bp.dot_ball_points
        + bp.economy_bonus
    )
    return bp


def _haul_bonus(wickets: int) -> int:
    """Cumulative haul bonuses: 3W→+4, 4W→+8, 5W→+12."""
    bonus = 0
    if wickets >= 5:
        bonus += 12
    if wickets >= 4:
        bonus += 8
    if wickets >= 3:
        bonus += 4
    return bonus


def _economy_rate_points(econ: float) -> int:
    """Tiered economy-rate bonus/penalty."""
    if econ < 5:
        return 6
    if econ < 6:
        return 4
    if econ < 7:
        return 2
    if econ < 10:
        return 0
    if econ < 11:
        return -2
    if econ < 12:
        return -4
    return -6


def _overs_to_balls(overs: float) -> int:
    """Convert overs notation (e.g. 3.3) to total balls (e.g. 21)."""
    whole = int(overs)
    fraction = round((overs - whole) * 10)
    return whole * 6 + fraction


# ── Fielding ───────────────────────────────────────────────────────────────────

def calculate_fielding_points(entry: FieldingEntry) -> FieldingPointsBreakdown:
    """Calculate fielding fantasy points."""
    fp = FieldingPointsBreakdown()

    # Catches: +8 each
    fp.catch_points = entry.catches * 8

    # 3-catch bonus: +4 (if 3+ catches)
    if entry.catches >= 3:
        fp.catch_bonus = 4

    # Stumpings: +12 each
    fp.stumping_points = entry.stumpings * 12

    # Run-outs
    fp.run_out_points = (
        entry.run_out_direct * 12
        + entry.run_out_indirect * 6
    )

    fp.total = (
        fp.catch_points
        + fp.catch_bonus
        + fp.stumping_points
        + fp.run_out_points
    )
    return fp


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_or_create(
    player_map: dict[str, PlayerPoints],
    name: str,
    team: str,
) -> PlayerPoints:
    """Get or create a PlayerPoints entry in the map."""
    if name not in player_map:
        player_map[name] = PlayerPoints(name=name, team=team)
    return player_map[name]


def _count_lbw_bowled(
    bowler_name: str,
    dismissals: list[DismissalDetail],
) -> int:
    """Count how many LBW or Bowled dismissals this bowler effected."""
    count = 0
    for d in dismissals:
        if d.bowler_name and d.bowler_name.lower() == bowler_name.lower():
            if d.dismissal_type in ("lbw", "bowled"):
                count += 1
    return count
