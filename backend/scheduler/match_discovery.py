"""
Match Discovery — scrapes the IPL 2026 schedule page from ESPNcricinfo
and upserts match records into the database.

The schedule page is static HTML, so we use requests + BeautifulSoup
(no Selenium needed).
"""

from __future__ import annotations

import re
import urllib3
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

# Suppress InsecureRequestWarning for corporate proxy environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from backend.db.base import SessionLocal
from backend.db.models import Match, MatchStatus
from backend.logger import get_logger

logger = get_logger(__name__)

SCHEDULE_URL = (
    "https://www.espncricinfo.com/series/ipl-2026-1510719/"
    "match-schedule-fixtures-and-results"
)

# Regex to extract match ID from scorecard URL
_MATCH_ID_RE = re.compile(r"-(\d{7})/full-scorecard")
# Regex to extract match number from title like "42nd Match"
_MATCH_NUM_RE = re.compile(r"(\d+)(?:st|nd|rd|th)\s+Match", re.IGNORECASE)


_IPL_LINK_RE = re.compile(
    r'href="(/series/ipl-2026-1510719/[^"]*?-(\d{7})/full-scorecard)"'
)
# Also match live-cricket-score links (ongoing/scheduled matches)
_IPL_LIVE_RE = re.compile(
    r'href="(/series/ipl-2026-1510719/[^"]*?-(\d{7})/live-cricket-score)"'
)
# Extract match slug parts: "team1-vs-team2-Nth-match-ID"
_SLUG_RE = re.compile(
    r"/series/ipl-2026-1510719/(.+)-(\d{7})/(?:full-scorecard|live-cricket-score)"
)


def _parse_schedule_page(html: str) -> list[dict]:
    """
    Parse the ESPN schedule page HTML and return a list of match dicts.

    Uses regex to find all IPL 2026 scorecard links AND live-cricket-score
    links. Matches with a scorecard link are marked completed; those with
    only a live link are marked scheduled (or ongoing).
    """
    matches: list[dict] = []
    seen_ids: set[str] = set()
    # Track which IDs have scorecard links
    scorecard_ids: set[str] = set()
    for m in _IPL_LINK_RE.finditer(html):
        scorecard_ids.add(m.group(2))

    # Process scorecard links first (completed matches)
    for href_match in _IPL_LINK_RE.finditer(html):
        href = href_match.group(1)
        espn_id = href_match.group(2)
        if espn_id in seen_ids:
            continue
        seen_ids.add(espn_id)
        _add_match(matches, href, espn_id, is_completed=True)

    # Process live-cricket-score links (ongoing/scheduled matches)
    for href_match in _IPL_LIVE_RE.finditer(html):
        href = href_match.group(1)
        espn_id = href_match.group(2)
        if espn_id in seen_ids:
            continue
        seen_ids.add(espn_id)
        # Build the scorecard URL even though it may not exist yet
        sc_href = href.replace("/live-cricket-score", "/full-scorecard")
        _add_match(matches, sc_href, espn_id, is_completed=False)

    logger.info("[DISCOVERY] Parsed %d IPL 2026 matches from schedule page", len(matches))
    return matches


def _add_match(matches: list[dict], href: str, espn_id: str, is_completed: bool):
    """Helper to parse a match URL slug and append to matches list."""
    full_url = f"https://www.espncricinfo.com{href}"
    slug_match = _SLUG_RE.search(href)
    title_text = ""
    team1 = None
    team2 = None
    match_num = None

    if slug_match:
        slug = slug_match.group(1)
        num_match = _MATCH_NUM_RE.search(slug.replace("-", " "))
        if num_match:
            match_num = int(num_match.group(1))
        teams_part = re.sub(r"-\d+(?:st|nd|rd|th)-match$", "", slug)
        if "-vs-" in teams_part:
            parts = teams_part.split("-vs-")
            team1 = parts[0].replace("-", " ").title()
            team2 = parts[1].replace("-", " ").title()
        title_text = slug.replace("-", " ").title()

    matches.append({
        "espn_match_id": espn_id,
        "match_number": match_num,
        "title": title_text or f"Match {espn_id}",
        "team1": team1,
        "team2": team2,
        "venue": None,
        "match_date": None,
        "scorecard_url": full_url,
        "result_text": None,
        "is_completed": is_completed,
    })


def discover_matches() -> int:
    """
    Fetch the IPL schedule page and upsert matches into the DB.
    
    Returns the number of newly discovered matches.
    """
    logger.info("[DISCOVERY] Starting match discovery from %s", SCHEDULE_URL)
    
    try:
        resp = requests.get(SCHEDULE_URL, timeout=30, verify=False, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error("[DISCOVERY] Failed to fetch schedule page: %s", e)
        return 0

    parsed = _parse_schedule_page(resp.text)
    if not parsed:
        logger.warning("[DISCOVERY] No matches parsed from schedule page")
        return 0

    new_count = 0
    db = SessionLocal()
    try:
        for m in parsed:
            existing = db.query(Match).filter_by(espn_match_id=m["espn_match_id"]).first()
            if existing:
                # Update status if match was scheduled and is now completed
                if existing.status == MatchStatus.SCHEDULED and m["is_completed"]:
                    existing.status = MatchStatus.COMPLETED
                    existing.scorecard_url = m["scorecard_url"]
                    existing.result_text = m["result_text"]
                    logger.info("[DISCOVERY] Match %s moved to COMPLETED", m["espn_match_id"])
                continue

            # Determine initial status
            # Matches 1-42 were manually extracted before this system
            status = MatchStatus.MANUALLY_EXTRACTED
            if m["match_number"] and m["match_number"] > 42:
                status = MatchStatus.COMPLETED if m["is_completed"] else MatchStatus.SCHEDULED
            elif m["match_number"] is None:
                # Can't determine match number — assume completed if has scorecard
                status = MatchStatus.COMPLETED if m["is_completed"] else MatchStatus.SCHEDULED

            new_match = Match(
                espn_match_id=m["espn_match_id"],
                match_number=m["match_number"],
                title=m["title"],
                team1=m["team1"],
                team2=m["team2"],
                venue=m["venue"],
                match_date=m["match_date"],
                scorecard_url=m["scorecard_url"],
                status=status,
                result_text=m["result_text"],
            )
            db.add(new_match)
            new_count += 1
            logger.debug("[DISCOVERY] New match: %s (%s)", m["title"], status)

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("[DISCOVERY] DB error during upsert")
        raise
    finally:
        db.close()

    logger.info("[DISCOVERY] Discovery complete — %d new matches added", new_count)
    return new_count
