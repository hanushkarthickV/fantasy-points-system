"""
Wrapper around gspread for all Google Sheets operations.
All direct gspread / google-auth calls are encapsulated here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import gspread
from google.oauth2.service_account import Credentials

from backend.logger import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetWrapper:
    """Encapsulates all Google Sheets read / write operations."""

    def __init__(self, credentials_path: str | Path):
        self._creds_path = Path(credentials_path)
        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None
        self._worksheet: Optional[gspread.Worksheet] = None

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self, spreadsheet_id: str) -> None:
        """Authenticate and open the spreadsheet by *spreadsheet_id*."""
        logger.info("[SHEET_WRAP] Authenticating with credentials: %s", self._creds_path)
        creds = Credentials.from_service_account_file(
            str(self._creds_path), scopes=SCOPES
        )
        self._client = gspread.authorize(creds)
        logger.info("[SHEET_WRAP] Authorized. Opening spreadsheet: %s", spreadsheet_id)
        try:
            self._spreadsheet = self._client.open_by_key(spreadsheet_id)
        except PermissionError:
            svc_email = creds.service_account_email
            raise PermissionError(
                f"Service account '{svc_email}' does not have access to spreadsheet "
                f"'{spreadsheet_id}'. Please share the spreadsheet with this email as Editor."
            )
        logger.info("[SHEET_WRAP] Connected to spreadsheet: %s", spreadsheet_id)

    def select_worksheet(self, name: str) -> None:
        """Select a specific worksheet (tab) by *name*."""
        self._ensure_spreadsheet()
        self._worksheet = self._spreadsheet.worksheet(name)
        logger.info("Selected worksheet: %s", name)

    # ── Reading ────────────────────────────────────────────────────────────────

    def get_all_records(self) -> list[dict[str, Any]]:
        """Return every row as a list of dicts (header → value).

        Handles sheets with duplicate or empty header columns by
        de-duplicating them (appending _2, _3 etc.) before building dicts.
        """
        self._ensure_worksheet()
        all_values = self._worksheet.get_all_values()
        if not all_values:
            return []

        raw_headers = all_values[0]
        logger.debug("[SHEET_WRAP] Raw headers: %s", raw_headers)

        # De-duplicate headers: empty→"_col{n}", duplicate→append suffix
        seen: dict[str, int] = {}
        headers: list[str] = []
        for idx, h in enumerate(raw_headers):
            if not h.strip():
                h = f"_col{idx + 1}"
            if h in seen:
                seen[h] += 1
                h = f"{h}_{seen[h]}"
            else:
                seen[h] = 1
            headers.append(h)

        logger.debug("[SHEET_WRAP] Resolved headers: %s", headers)

        records = []
        for row in all_values[1:]:
            # Pad short rows with empty strings
            padded = row + [""] * (len(headers) - len(row))
            records.append(dict(zip(headers, padded)))
        return records

    def get_column_values(self, column_name: str) -> list[str]:
        """Return all values in a column identified by its header *column_name*."""
        self._ensure_worksheet()
        header_row = self._worksheet.row_values(1)
        col_index = header_row.index(column_name) + 1  # 1-indexed
        return self._worksheet.col_values(col_index)[1:]  # skip header

    def get_cell_value(self, row: int, col: int) -> str:
        """Return the value of the cell at (*row*, *col*) (1-indexed)."""
        self._ensure_worksheet()
        return self._worksheet.cell(row, col).value or ""

    def find_column_index(self, column_name: str) -> int:
        """Return the 1-indexed column number for *column_name*."""
        self._ensure_worksheet()
        header_row = self._worksheet.row_values(1)
        return header_row.index(column_name) + 1

    # ── Writing ────────────────────────────────────────────────────────────────

    def update_cell(self, row: int, col: int, value: Any) -> None:
        """Update a single cell at (*row*, *col*) with *value*."""
        self._ensure_worksheet()
        self._worksheet.update_cell(row, col, value)
        logger.debug("Updated cell (%d, %d) → %s", row, col, value)

    def batch_update_cells(self, updates: list[dict]) -> None:
        """
        Batch-update multiple cells.

        Each item in *updates* must have keys: ``row``, ``col``, ``value``.
        """
        self._ensure_worksheet()
        cells = []
        for u in updates:
            cell = gspread.Cell(row=u["row"], col=u["col"], value=u["value"])
            cells.append(cell)
        if cells:
            self._worksheet.update_cells(cells)
            logger.info("Batch-updated %d cells", len(cells))

    # ── Search ─────────────────────────────────────────────────────────────────

    def find_row_by_value(self, column_name: str, value: str) -> Optional[int]:
        """
        Return the 1-indexed row number where *column_name* equals *value*,
        or ``None`` if not found.
        """
        self._ensure_worksheet()
        col_idx = self.find_column_index(column_name)
        col_values = self._worksheet.col_values(col_idx)
        for i, v in enumerate(col_values):
            if v == value:
                return i + 1  # 1-indexed
        return None

    # ── Internals ──────────────────────────────────────────────────────────────

    def _ensure_spreadsheet(self) -> None:
        if self._spreadsheet is None:
            raise RuntimeError("Not connected. Call connect() first.")

    def _ensure_worksheet(self) -> None:
        if self._worksheet is None:
            raise RuntimeError("No worksheet selected. Call select_worksheet() first.")
