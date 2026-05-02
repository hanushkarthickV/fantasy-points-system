"""
Match Discovery — scrapes the IPL 2026 schedule page from ESPNcricinfo
and upserts match records into the database.

The schedule page is static HTML, so we use requests + BeautifulSoup
(no Selenium needed).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

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


def _parse_schedule_page(html: str) -> list[dict]:
    """
    Parse the ESPN schedule page HTML and return a list of match dicts.
    
    Each dict has:
      - espn_match_id: str
      - match_number: int | None
      - title: str
      - team1: str | None
      - team2: str | None
      - venue: str | None
      - match_date: datetime | None
      - scorecard_url: str | None
      - result_text: str | None
      - is_completed: bool
    """
    soup = BeautifulSoup(html, "html.parser")
    matches: list[dict] = []

    # Look for match cards — ESPN uses div containers with match info
    # Each match card has a link to the scorecard and match details
    match_cards = soup.select("div[class*='MatchCardContainer']")
    
    if not match_cards:
        # Alternative selector: look for schedule list items
        match_cards = soup.select("div.ds-p-0 a[href*='/full-scorecard']")
        if not match_cards:
            # Try another pattern: all links to full-scorecard
            scorecard_links = soup.find_all("a", href=re.compile(r"/full-scorecard"))
            for link in scorecard_links:
                href = link.get("href", "")
                mid_match = _MATCH_ID_RE.search(href)
                if not mid_match:
                    continue
                espn_id = mid_match.group(1)
                
                # Walk up to find the card container
                card = link.find_parent("div", class_=re.compile(r"ds-"))
                title_text = ""
                if card:
                    # Try to find match title
                    title_el = card.find("p", class_=re.compile(r"ds-text-tight"))
                    title_text = title_el.get_text(strip=True) if title_el else ""

                match_num = None
                num_match = _MATCH_NUM_RE.search(title_text)
                if num_match:
                    match_num = int(num_match.group(1))

                full_url = f"https://www.espncricinfo.com{href}" if href.startswith("/") else href

                matches.append({
                    "espn_match_id": espn_id,
                    "match_number": match_num,
                    "title": title_text or f"Match {espn_id}",
                    "team1": None,
                    "team2": None,
                    "venue": None,
                    "match_date": None,
                    "scorecard_url": full_url,
                    "result_text": None,
                    "is_completed": True,  # has scorecard → completed
                })
            
            # Also look for scheduled matches (no scorecard link)
            # These won't have /full-scorecard URLs yet
            logger.info("[DISCOVERY] Found %d matches via scorecard links", len(matches))
            return matches

    # Process structured match cards
    for card in match_cards:
        scorecard_link = card.find("a", href=re.compile(r"/full-scorecard"))
        if not scorecard_link:
            continue
        href = scorecard_link.get("href", "")
        mid_match = _MATCH_ID_RE.search(href)
        if not mid_match:
            continue
        espn_id = mid_match.group(1)
        full_url = f"https://www.espncricinfo.com{href}" if href.startswith("/") else href

        # Extract details from card
        title_text = ""
        title_el = card.find(string=re.compile(r"\d+(?:st|nd|rd|th)\s+Match"))
        if title_el:
            title_text = title_el.strip()

        match_num = None
        num_match = _MATCH_NUM_RE.search(title_text)
        if num_match:
            match_num = int(num_match.group(1))

        # Teams
        team_els = card.select("p[class*='TeamName']")
        team1 = team_els[0].get_text(strip=True) if len(team_els) > 0 else None
        team2 = team_els[1].get_text(strip=True) if len(team_els) > 1 else None

        # Result
        result_el = card.find(string=re.compile(r"(won|tied|no result)", re.IGNORECASE))
        result_text = result_el.strip() if result_el else None

        matches.append({
            "espn_match_id": espn_id,
            "match_number": match_num,
            "title": title_text or f"Match {espn_id}",
            "team1": team1,
            "team2": team2,
            "venue": None,
            "match_date": None,
            "scorecard_url": full_url,
            "result_text": result_text,
            "is_completed": result_text is not None,
        })

    logger.info("[DISCOVERY] Parsed %d match cards from schedule page", len(matches))
    return matches


def discover_matches() -> int:
    """
    Fetch the IPL schedule page and upsert matches into the DB.
    
    Returns the number of newly discovered matches.
    """
    logger.info("[DISCOVERY] Starting match discovery from %s", SCHEDULE_URL)
    
    try:
        resp = requests.get(SCHEDULE_URL, timeout=30, headers={
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
