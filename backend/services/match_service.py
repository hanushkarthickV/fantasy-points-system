"""
Orchestration service — ties together scraping, points calculation,
and sheet updates into a coherent workflow.

Persists intermediate JSONs to ``data/matches/<match_id>/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.config import DATA_DIR
from backend.logger import get_logger
from backend.engine.points_calculator import calculate_match_points
from backend.models.schemas import (
    MatchMetadata,
    MatchPoints,
    PlayerEdit,
    SheetUpdateResponse,
)
from backend.scraper.scorecard_scraper import scrape_scorecard, ProgressCallback
from backend.services.sheet_service import SheetService

logger = get_logger(__name__)


class MatchService:
    """High-level API consumed by the route handlers."""

    def __init__(self):
        self._sheet_service = SheetService()

    # ── Step 1: Scrape ─────────────────────────────────────────────────────────

    def scrape_match(
        self, url: str, on_progress: ProgressCallback = None,
    ) -> MatchMetadata:
        """Scrape a match scorecard and persist metadata JSON."""
        metadata = scrape_scorecard(url, on_progress=on_progress)
        self._save_match_json(metadata.match_id, "metadata.json", metadata.model_dump())
        logger.info("Scraped and saved metadata for match %s", metadata.match_id)
        return metadata

    # ── Step 2: Calculate Points ───────────────────────────────────────────────

    def calculate_points(self, match_id: str) -> MatchPoints:
        """Load metadata, calculate points, and persist points JSON."""
        metadata = self._load_metadata(match_id)

        # Fetch bowler names from the sheet for duck-penalty exemption
        try:
            bowler_names = self._sheet_service.get_bowler_names()
        except Exception:
            logger.warning("Could not fetch bowler names from sheet; skipping duck exemption")
            bowler_names = set()

        points = calculate_match_points(metadata, bowler_names)
        self._save_match_json(match_id, "points.json", points.model_dump())
        logger.info("Calculated and saved points for match %s", match_id)
        return points

    # ── Step 3: Update Sheet ───────────────────────────────────────────────────

    def update_sheet(self, match_id: str) -> SheetUpdateResponse:
        """Load points JSON and push updates to Google Sheets."""
        points = self._load_points(match_id)
        result = self._sheet_service.update_points_from_match(points)
        self._save_match_json(match_id, "update_result.json", result.model_dump())
        logger.info(
            "Updated sheet for match %s: %d players updated, %d unmatched",
            match_id,
            len(result.updated_players),
            len(result.unmatched_players),
        )
        return result

    # ── Step 4: Edit Players ───────────────────────────────────────────────────

    def edit_players(self, match_id: str, edits: list[PlayerEdit]) -> MatchPoints:
        """Apply name/points edits to the saved points JSON and re-save.

        When renaming a player to a name that already exists, the entries are
        merged: points are summed and only one Playing XI bonus is retained.
        """
        points = self._load_points(match_id)
        player_map = {p.name: p for p in points.players}

        for edit in edits:
            player = player_map.get(edit.original_name)
            if not player:
                logger.warning("Edit target '%s' not found in match %s", edit.original_name, match_id)
                continue
            if edit.new_name is not None and edit.new_name != edit.original_name:
                del player_map[edit.original_name]
                if edit.new_name in player_map:
                    # Merge into existing player — remove duplicate Playing XI bonus
                    existing = player_map[edit.new_name]
                    base_points = player.total_points - player.playing_xi_bonus
                    existing.total_points += base_points
                    # Merge breakdowns
                    if player.batting:
                        if existing.batting:
                            existing.batting.run_points += player.batting.run_points
                            existing.batting.four_bonus += player.batting.four_bonus
                            existing.batting.six_bonus += player.batting.six_bonus
                            existing.batting.milestone_bonus += player.batting.milestone_bonus
                            existing.batting.duck_penalty += player.batting.duck_penalty
                            existing.batting.strike_rate_bonus += player.batting.strike_rate_bonus
                            existing.batting.total += player.batting.total
                        else:
                            existing.batting = player.batting
                    if player.bowling:
                        if existing.bowling:
                            existing.bowling.wicket_points += player.bowling.wicket_points
                            existing.bowling.maiden_bonus += player.bowling.maiden_bonus
                            existing.bowling.lbw_bowled_bonus += player.bowling.lbw_bowled_bonus
                            existing.bowling.haul_bonus += player.bowling.haul_bonus
                            existing.bowling.dot_ball_points += player.bowling.dot_ball_points
                            existing.bowling.economy_bonus += player.bowling.economy_bonus
                            existing.bowling.total += player.bowling.total
                        else:
                            existing.bowling = player.bowling
                    if player.fielding:
                        if existing.fielding:
                            existing.fielding.catch_points += player.fielding.catch_points
                            existing.fielding.catch_bonus += player.fielding.catch_bonus
                            existing.fielding.stumping_points += player.fielding.stumping_points
                            existing.fielding.run_out_points += player.fielding.run_out_points
                            existing.fielding.total += player.fielding.total
                        else:
                            existing.fielding = player.fielding
                    logger.info(
                        "Merged '%s' into '%s' — new total: %d",
                        edit.original_name, edit.new_name, existing.total_points,
                    )
                else:
                    player.name = edit.new_name
                    player_map[edit.new_name] = player
            if edit.new_total_points is not None:
                target = player_map.get(edit.new_name or edit.original_name)
                if target:
                    target.total_points = edit.new_total_points

        points.players = list(player_map.values())
        self._save_match_json(match_id, "points.json", points.model_dump())
        logger.info("Edited and saved points for match %s", match_id)
        return points

    # ── Step 5: Retry Unmatched ──────────────────────────────────────────────

    def retry_unmatched(
        self, match_id: str, name_corrections: dict[str, str]
    ) -> SheetUpdateResponse:
        """
        Re-attempt sheet update for unmatched players using corrected names.
        name_corrections: {scraped_display_name: exact_sheet_name}
        """
        points = self._load_points(match_id)
        result = self._sheet_service.update_specific_players(
            points, name_corrections
        )
        self._save_match_json(match_id, "retry_result.json", result.model_dump())
        return result

    # ── Loaders ────────────────────────────────────────────────────────────────

    def get_metadata(self, match_id: str) -> MatchMetadata:
        """Return persisted metadata for a match."""
        return self._load_metadata(match_id)

    def get_points(self, match_id: str) -> MatchPoints:
        """Return persisted points for a match."""
        return self._load_points(match_id)

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _match_dir(match_id: str) -> Path:
        """Return ``data/matches/<match_id>/``, creating it if needed."""
        d = DATA_DIR / "matches" / match_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_metadata(self, match_id: str) -> MatchMetadata:
        path = self._match_dir(match_id) / "metadata.json"
        if not path.exists():
            raise FileNotFoundError(f"Metadata not found for match {match_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return MatchMetadata(**data)

    def _load_points(self, match_id: str) -> MatchPoints:
        path = self._match_dir(match_id) / "points.json"
        if not path.exists():
            raise FileNotFoundError(f"Points not found for match {match_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return MatchPoints(**data)

    def _save_match_json(self, match_id: str, filename: str, data: dict) -> Path:
        """Persist a JSON file under ``data/matches/<match_id>/<filename>``."""
        path = self._match_dir(match_id) / filename
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("Saved %s", path)
        return path
