"""
Wrapper around BeautifulSoup for all HTML parsing operations.
All direct BS4 calls are encapsulated here.
"""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup, Tag


class ElementWrapper:
    """Provides convenient methods over a BeautifulSoup document / element."""

    def __init__(self, source: str | Tag):
        if isinstance(source, str):
            self._soup = BeautifulSoup(source, "html.parser")
            self._element: Tag = self._soup
        else:
            self._soup = None
            self._element = source

    # ── Querying ───────────────────────────────────────────────────────────────

    def find(self, css_selector: str) -> Optional["ElementWrapper"]:
        """Return the first element matching *css_selector*, or ``None``."""
        tag = self._element.select_one(css_selector)
        return ElementWrapper(tag) if tag else None

    def find_all(self, css_selector: str) -> list["ElementWrapper"]:
        """Return all elements matching *css_selector*."""
        tags = self._element.select(css_selector)
        return [ElementWrapper(t) for t in tags]

    # ── Text / Attributes ──────────────────────────────────────────────────────

    def get_text(self, strip: bool = True, separator: str = "") -> str:
        """Return the combined text of this element."""
        text = self._element.get_text(separator=separator)
        if strip:
            text = text.strip()
        # collapse multiple whitespace
        text = re.sub(r"\s+", " ", text)
        return text

    def get_attribute(self, name: str) -> Optional[str]:
        """Return the value of attribute *name*."""
        return self._element.get(name)

    def get_href(self) -> Optional[str]:
        """Shorthand for ``get_attribute('href')``."""
        return self.get_attribute("href")

    # ── Table Helpers ──────────────────────────────────────────────────────────

    def get_table_rows(self) -> list["ElementWrapper"]:
        """Return all ``<tr>`` elements inside this element (typically a ``<tbody>``)."""
        rows = self._element.find_all("tr", recursive=True)
        return [ElementWrapper(r) for r in rows if not self._is_hidden_row(r)]

    def get_table_cells(self) -> list["ElementWrapper"]:
        """Return all ``<td>`` / ``<th>`` elements inside this row."""
        cells = self._element.find_all(["td", "th"], recursive=False)
        return [ElementWrapper(c) for c in cells]

    # ── Predicates ─────────────────────────────────────────────────────────────

    def has_class(self, class_name: str) -> bool:
        """Check whether this element has *class_name*."""
        classes = self._element.get("class", [])
        return class_name in classes

    def exists(self) -> bool:
        """Return ``True`` if the underlying tag is not None."""
        return self._element is not None

    # ── Raw access ─────────────────────────────────────────────────────────────

    @property
    def tag(self) -> Tag:
        """Expose the raw BS4 Tag for edge-case operations."""
        return self._element

    @property
    def inner_html(self) -> str:
        """Return the inner HTML of this element."""
        return self._element.decode_contents()

    # ── Private ────────────────────────────────────────────────────────────────

    @staticmethod
    def _is_hidden_row(row: Tag) -> bool:
        """Detect rows with class ``ds-hidden`` (ESPNcricinfo hides commentary rows)."""
        classes = row.get("class", [])
        return "ds-hidden" in classes
