"""
Service for reading from and updating the Google Sheets "database".

Handles fuzzy matching of scraped player names against the spreadsheet,
reading existing points, and writing updated points.
"""

from __future__ import annotations

from typing import Any

from thefuzz import fuzz

from backend.logger import get_logger
from backend.config import (
    FUZZY_AUTO_MATCH_THRESHOLD,
    GOOGLE_CREDENTIALS_PATH,
    PLAYER_NAME_COLUMN,
    POINTS_COLUMN,
    SPECIALISM_COLUMN,
    SPREADSHEET_ID,
    WORKSHEET_NAME,
)
from backend.models.schemas import (
    MatchPoints,
    PlayerUpdateResult,
    SheetUpdateResponse,
)
from backend.wrappers.sheet_wrapper import SheetWrapper

logger = get_logger(__name__)


class SheetService:
    """Reads and updates player points in Google Sheets."""

    def __init__(self):
        self._sheet = SheetWrapper(GOOGLE_CREDENTIALS_PATH)
        self._connected = False

    def _ensure_connected(self) -> None:
        if not self._connected:
            logger.info("[SHEET_SVC] Connecting to spreadsheet %s, worksheet %s", SPREADSHEET_ID, WORKSHEET_NAME)
            self._sheet.connect(SPREADSHEET_ID)
            self._sheet.select_worksheet(WORKSHEET_NAME)
            self._connected = True
            logger.info("[SHEET_SVC] Connected successfully")

    # ── Reading ────────────────────────────────────────────────────────────────

    def get_all_players(self) -> list[dict[str, Any]]:
        """Return all rows from the auction list sheet."""
        self._ensure_connected()
        return self._sheet.get_all_records()

    def get_bowler_names(self) -> set[str]:
        """
        Return a set of player names whose Specialism is 'BOWLER'.
        Used for duck-penalty exemption.
        """
        self._ensure_connected()
        records = self._sheet.get_all_records()
        bowlers = set()
        for r in records:
            specialism = str(r.get(SPECIALISM_COLUMN, "")).strip().upper()
            if specialism == "BOWLER":
                player_name = str(r.get(PLAYER_NAME_COLUMN, "")).strip()
                if player_name:
                    bowlers.add(player_name)
        return bowlers

    # ── Fuzzy Matching & Updating ──────────────────────────────────────────────

    def update_points_from_match(
        self, match_points: MatchPoints
    ) -> SheetUpdateResponse:
        """
        Fuzzy-match each player from *match_points* against the sheet,
        add their points to existing ``DreamPoints``, and return a diff.
        """
        self._ensure_connected()
        records = self._sheet.get_all_records()
        points_col = self._sheet.find_column_index(POINTS_COLUMN)
        name_col = self._sheet.find_column_index(PLAYER_NAME_COLUMN)
        spec_col = self._sheet.find_column_index(SPECIALISM_COLUMN)

        # Build lookup: sheet_name → (row_index_1based, record)
        sheet_lookup: dict[str, tuple[int, dict]] = {}
        for i, rec in enumerate(records):
            pname = str(rec.get(PLAYER_NAME_COLUMN, "")).strip()
            if pname:
                sheet_lookup[pname] = (i + 2, rec)  # +2: header=row1, 0-indexed→1-indexed

        updated: list[PlayerUpdateResult] = []
        unmatched: list[str] = []
        batch_updates: list[dict] = []

        logger.info("[SHEET_SVC] Processing %d players from match %s", len(match_points.players), match_points.match_id)

        for player in match_points.players:
            if player.total_points == 0:
                logger.debug("[SHEET_SVC] Skipping %s (0 points)", player.name)
                continue

            best_match, best_score, best_key = self._fuzzy_find(
                player.name, sheet_lookup
            )
            logger.debug("[SHEET_SVC] Fuzzy: '%s' → '%s' (score=%d)", player.name, best_match, best_score)

            if best_score >= FUZZY_AUTO_MATCH_THRESHOLD and best_key:
                row_idx, rec = sheet_lookup[best_key]
                prev_points = _safe_float(rec.get(POINTS_COLUMN, 0))
                new_points = prev_points + player.total_points
                specialism = str(rec.get(SPECIALISM_COLUMN, ""))

                batch_updates.append({
                    "row": row_idx,
                    "col": points_col,
                    "value": new_points,
                })

                updated.append(PlayerUpdateResult(
                    scraped_name=player.name,
                    matched_name=best_key,
                    match_score=best_score,
                    previous_points=prev_points,
                    added_points=player.total_points,
                    new_points=new_points,
                    specialism=specialism,
                ))
            else:
                unmatched.append(
                    f"{player.name} (best: {best_match}, score: {best_score})"
                )
                logger.warning(
                    "No confident match for '%s' (best: '%s' @ %d)",
                    player.name,
                    best_match,
                    best_score,
                )

        # Write all updates in one batch
        if batch_updates:
            self._sheet.batch_update_cells(batch_updates)
            logger.info("Updated %d players in sheet", len(batch_updates))

        return SheetUpdateResponse(
            match_id=match_points.match_id,
            updated_players=updated,
            unmatched_players=unmatched,
        )

    # ── Fuzzy Matching ─────────────────────────────────────────────────────────

    @staticmethod
    def _fuzzy_find(
        scraped_name: str,
        sheet_lookup: dict[str, tuple[int, dict]],
    ) -> tuple[str, int, str | None]:
        """
        Find the best fuzzy match for *scraped_name* in *sheet_lookup*.
        Returns (best_name, best_score, best_key_or_None).
        """
        best_name = ""
        best_score = 0
        best_key: str | None = None

        for sheet_name in sheet_lookup:
            score = fuzz.token_sort_ratio(
                scraped_name.lower(), sheet_name.lower()
            )
            if score > best_score:
                best_score = score
                best_name = sheet_name
                best_key = sheet_name

        return best_name, best_score, best_key


def _safe_float(val: Any) -> float:
    """Convert a value to float, defaulting to 0.0."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
