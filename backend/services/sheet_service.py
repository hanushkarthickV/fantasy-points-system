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
    SUMMARY_SORT_COLUMN,
    SUMMARY_WORKSHEET_NAME,
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
            self._sort_summary_table()

        return SheetUpdateResponse(
            match_id=match_points.match_id,
            updated_players=updated,
            unmatched_players=unmatched,
        )

    # ── Retry Unmatched (exact name match) ─────────────────────────────────────

    def update_specific_players(
        self,
        match_points: MatchPoints,
        name_corrections: dict[str, str],
    ) -> SheetUpdateResponse:
        """
        Update sheet for specific players using exact corrected names.
        name_corrections: {scraped_display_name: exact_sheet_name}
        """
        self._ensure_connected()
        records = self._sheet.get_all_records()
        points_col = self._sheet.find_column_index(POINTS_COLUMN)
        spec_col = self._sheet.find_column_index(SPECIALISM_COLUMN)

        # Build sheet row lookup — keyed by original name AND lowercase for case-insensitive matching
        sheet_lookup: dict[str, tuple[int, dict]] = {}
        sheet_lookup_lower: dict[str, str] = {}  # lowercase → original sheet name
        for i, rec in enumerate(records):
            pname = str(rec.get(PLAYER_NAME_COLUMN, "")).strip()
            if pname:
                sheet_lookup[pname] = (i + 2, rec)
                sheet_lookup_lower[pname.lower()] = pname

        # Build player points lookup from match  (strip " (best: ...)" from display name)
        player_points_map: dict[str, int] = {}
        for p in match_points.players:
            player_points_map[p.name] = p.total_points

        updated: list[PlayerUpdateResult] = []
        still_unmatched: list[str] = []
        batch_updates: list[dict] = []

        for display_name, corrected_name in name_corrections.items():
            # Extract the actual scraped name (strip " (best: ..., score: ..)" suffix)
            scraped_name = display_name.split(" (best:")[0].strip() if " (best:" in display_name else display_name

            pts = player_points_map.get(scraped_name, 0)

            # Case-insensitive lookup: try exact first, then lowercase
            actual_key = corrected_name if corrected_name in sheet_lookup else sheet_lookup_lower.get(corrected_name.lower())

            if actual_key and actual_key in sheet_lookup:
                row_idx, rec = sheet_lookup[actual_key]
                prev_points = _safe_float(rec.get(POINTS_COLUMN, 0))
                new_points = prev_points + pts
                specialism = str(rec.get(SPECIALISM_COLUMN, ""))

                batch_updates.append({"row": row_idx, "col": points_col, "value": new_points})
                updated.append(PlayerUpdateResult(
                    scraped_name=scraped_name,
                    matched_name=actual_key,
                    match_score=100,
                    previous_points=prev_points,
                    added_points=pts,
                    new_points=new_points,
                    specialism=specialism,
                ))
            else:
                # Preserve the ORIGINAL display key so frontend can track by stable key
                still_unmatched.append(display_name)

        if batch_updates:
            self._sheet.batch_update_cells(batch_updates)
            logger.info("Retry: updated %d players in sheet", len(batch_updates))
            self._sort_summary_table()

        return SheetUpdateResponse(
            match_id=match_points.match_id,
            updated_players=updated,
            unmatched_players=still_unmatched,
        )

    # ── Summary Table Sorting ─────────────────────────────────────────────────

    def _sort_summary_table(self) -> None:
        """Sort the Summary-PointsTable sheet by Dream11 Points descending."""
        try:
            self._sheet.sort_worksheet_by_column(
                SUMMARY_WORKSHEET_NAME, SUMMARY_SORT_COLUMN, ascending=False
            )
            logger.info("[SHEET_SVC] Sorted summary table by %s", SUMMARY_SORT_COLUMN)
        except Exception as exc:
            logger.warning("[SHEET_SVC] Failed to sort summary table: %s", exc)

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
