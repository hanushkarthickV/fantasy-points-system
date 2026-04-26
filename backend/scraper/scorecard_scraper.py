"""
Scrapes ESPNcricinfo full-scorecard pages and returns structured MatchMetadata.

Uses BrowserWrapper for page loading and ElementWrapper for HTML parsing.
"""

from __future__ import annotations

import re
from typing import Optional

from backend.logger import get_logger
from backend.models.schemas import (
    BattingEntry,
    BowlingEntry,
    DismissalDetail,
    FieldingEntry,
    InningsData,
    MatchMetadata,
)
from backend.wrappers.browser_wrapper import BrowserWrapper
from backend.wrappers.element_wrapper import ElementWrapper

logger = get_logger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────

def scrape_scorecard(url: str) -> MatchMetadata:
    """
    Open the ESPNcricinfo scorecard at *url*, parse it, and return a
    fully-populated ``MatchMetadata`` object.
    """
    match_id = _extract_match_id(url)
    logger.info("[SCRAPER] Starting scrape for match_id=%s, url=%s", match_id, url)

    with BrowserWrapper() as browser:
        browser.open(url)
        logger.debug("[SCRAPER] Page loaded, waiting for scorecard table...")
        browser.wait_for_element("table.ci-scorecard-table")
        html = browser.get_page_source()
        logger.info("[SCRAPER] Got page source (%d chars)", len(html))

    result = _parse_scorecard_html(html, match_id, url)
    logger.info("[SCRAPER] Parse complete: %d innings, teams: %s vs %s", len(result.innings), result.team1, result.team2)
    return result


def parse_scorecard_from_html(html: str, url: str) -> MatchMetadata:
    """
    Parse a scorecard directly from an HTML string (useful for local MHTML files).
    """
    match_id = _extract_match_id(url)
    return _parse_scorecard_html(html, match_id, url)


# ── Internal Parsing ───────────────────────────────────────────────────────────

def _parse_scorecard_html(html: str, match_id: str, url: str) -> MatchMetadata:
    """Master parse routine that assembles all innings data."""
    doc = ElementWrapper(html)

    # Match-level info
    title_el = doc.find("h1")
    match_title = title_el.get_text() if title_el else "Unknown Match"

    result_el = doc.find("p.ds-text-body-1.ds-font-medium.ds-truncate")
    result = result_el.get_text() if result_el else ""

    # Extract venue and date from title (format: "... at Venue, Month DD, YYYY")
    venue, date = _extract_venue_date(match_title)

    # Extract team names from the score header
    team_names = _extract_team_names(doc)
    team1 = team_names[0] if len(team_names) > 0 else "Team 1"
    team2 = team_names[1] if len(team_names) > 1 else "Team 2"

    # Parse innings containers — each has batting table + bowling table
    innings_containers = doc.find_all("div.ds-mb-4.ds-border-t")
    logger.debug("[SCRAPER] Found %d div.ds-mb-4.ds-border-t containers", len(innings_containers))

    # Filter to only those that contain a batting table
    innings_divs = [
        c for c in innings_containers
        if c.find("table.ci-scorecard-table") is not None
    ]
    logger.debug("[SCRAPER] After filtering for batting tables: %d innings divs", len(innings_divs))

    innings_list: list[InningsData] = []
    for idx, container in enumerate(innings_divs):
        team_name = team1 if idx == 0 else team2
        logger.info("[SCRAPER] Parsing innings %d for team: %s", idx + 1, team_name)
        innings_data = _parse_innings(container, team_name)
        logger.info(
            "[SCRAPER]   Batting: %d entries, Bowling: %d entries, Fielding: %d entries, DNB: %d",
            len(innings_data.batting), len(innings_data.bowling),
            len(innings_data.fielding), len(innings_data.did_not_bat),
        )
        innings_list.append(innings_data)

    # ── Post-process: resolve short names in dismissals & fielding ────────
    _resolve_short_names(innings_list)

    return MatchMetadata(
        match_id=match_id,
        match_title=match_title,
        venue=venue,
        date=date,
        team1=team1,
        team2=team2,
        result=result,
        innings=innings_list,
        url=url,
    )


def _extract_team_names(doc: ElementWrapper) -> list[str]:
    """Pull team names from the ci-team-score divs in the match header."""
    score_rows = doc.find_all("div.ci-team-score")
    names = []
    for row in score_rows:
        link = row.find("a[href*='/team/'] span")
        if link:
            names.append(link.get_text())
    return names


def _parse_innings(container: ElementWrapper, team_name: str) -> InningsData:
    """Parse a single innings container into InningsData."""
    # ── Batting ────────────────────────────────────────────────────────────────
    batting_table = container.find("table.ci-scorecard-table")
    batting_entries, dismissal_details = _parse_batting_table(batting_table)

    # ── Extras & Total from batting table footer rows ──────────────────────────
    extras = 0
    total_runs = 0
    total_wickets = 0
    total_overs = 0.0
    _extract_totals_from_batting(batting_table, locals_dict := {})
    extras = locals_dict.get("extras", 0)
    total_runs = locals_dict.get("total_runs", 0)
    total_wickets = locals_dict.get("total_wickets", 0)
    total_overs = locals_dict.get("total_overs", 0.0)

    # ── Did Not Bat ────────────────────────────────────────────────────────────
    did_not_bat = _parse_did_not_bat(batting_table)

    # ── Bowling (the table that follows the batting table) ─────────────────────
    all_tables = container.find_all("table")
    bowling_entries: list[BowlingEntry] = []
    for t in all_tables:
        header = t.find("th")
        if header and "bowling" in header.get_text().lower():
            bowling_entries = _parse_bowling_table(t)
            break

    # ── Fielding (derived from dismissals) ─────────────────────────────────────
    fielding_entries = _derive_fielding(dismissal_details)

    return InningsData(
        team_name=team_name,
        batting=batting_entries,
        bowling=bowling_entries,
        fielding=fielding_entries,
        did_not_bat=did_not_bat,
        dismissals=dismissal_details,
        extras=extras,
        total_runs=total_runs,
        total_wickets=total_wickets,
        total_overs=total_overs,
    )


# ── Batting Parsing ────────────────────────────────────────────────────────────

def _parse_batting_table(table: ElementWrapper) -> tuple[list[BattingEntry], list[DismissalDetail]]:
    """Parse batting rows from the scorecard table."""
    if table is None:
        return [], []

    batting: list[BattingEntry] = []
    dismissals: list[DismissalDetail] = []
    tbody = table.find("tbody")
    if tbody is None:
        return [], []

    rows = tbody.get_table_rows()

    for row_idx, row in enumerate(rows):
        cells = row.get_table_cells()
        if len(cells) < 8:
            logger.debug("[SCRAPER] Batting row %d: only %d cells, skipping", row_idx, len(cells))
            continue

        first_cell_text = cells[0].get_text()

        # Skip Extras row, Total row, DNB row, FOW row
        if first_cell_text.lower() in ("extras", "total", ""):
            continue
        if "did not bat" in first_cell_text.lower():
            continue
        if "fall of wickets" in first_cell_text.lower():
            continue

        # Check if this is a batter row — must have a link to a cricketer
        name_link = cells[0].find("a[href*='/cricketers/']")
        if name_link is None:
            logger.debug("[SCRAPER] Batting row %d: no cricketer link found in '%s'", row_idx, first_cell_text)
            continue

        raw_name = name_link.get_text()
        name = _clean_player_name(raw_name)

        # Dismissal text from 2nd cell
        dismissal_text = cells[1].get_text()

        # Stats from remaining cells
        runs = _safe_int(cells[2].get_text())
        balls = _safe_int(cells[3].get_text())
        minutes = _safe_int(cells[4].get_text())
        fours = _safe_int(cells[5].get_text())
        sixes = _safe_int(cells[6].get_text())
        sr = _safe_float(cells[7].get_text())

        is_not_out = "not out" in dismissal_text.lower()

        logger.debug("[SCRAPER] Batter: %s | R=%d B=%d 4s=%d 6s=%d SR=%.2f | %s", name, runs, balls, fours, sixes, sr, dismissal_text)

        batting.append(BattingEntry(
            name=name,
            dismissal=dismissal_text,
            runs=runs,
            balls=balls,
            minutes=minutes,
            fours=fours,
            sixes=sixes,
            strike_rate=sr,
            is_not_out=is_not_out,
        ))

        dismissal_detail = _parse_dismissal(name, dismissal_text)
        dismissals.append(dismissal_detail)

    logger.debug("[SCRAPER] Parsed %d batters from table", len(batting))
    return batting, dismissals


def _extract_totals_from_batting(table: ElementWrapper, locals_dict: dict) -> None:
    """Extract extras, total runs, wickets, overs from the batting table footer."""
    if table is None:
        return

    tbody = table.find("tbody")
    if tbody is None:
        return

    # We need to look at ALL tr including hidden ones for extras/total
    all_rows = table.tag.find_all("tr") if table.tag else []

    for row_tag in all_rows:
        row = ElementWrapper(row_tag)
        cells = row.get_table_cells()
        if not cells:
            continue

        first_text = cells[0].get_text().lower().strip()

        if first_text == "extras" and len(cells) >= 3:
            extras_val = _safe_int(cells[2].get_text())
            locals_dict["extras"] = extras_val

        if first_text == "total" and len(cells) >= 3:
            # Total row has: "Total", overs info, score like "228/6"
            score_text = cells[2].get_text()
            match = re.search(r"(\d+)/(\d+)", score_text)
            if match:
                locals_dict["total_runs"] = int(match.group(1))
                locals_dict["total_wickets"] = int(match.group(2))

            overs_text = cells[1].get_text()
            overs_match = re.search(r"([\d.]+)\s*Ov", overs_text)
            if overs_match:
                locals_dict["total_overs"] = float(overs_match.group(1))


# ── Bowling Parsing ────────────────────────────────────────────────────────────

def _parse_bowling_table(table: ElementWrapper) -> list[BowlingEntry]:
    """Parse bowling rows from the bowling table."""
    entries: list[BowlingEntry] = []
    tbody = table.find("tbody")
    if tbody is None:
        return entries

    rows = tbody.get_table_rows()
    for row in rows:
        cells = row.get_table_cells()
        if len(cells) < 9:
            continue

        name_link = cells[0].find("a[href*='/cricketers/']")
        if name_link is None:
            continue

        name = _clean_player_name(name_link.get_text())
        overs = _safe_float(cells[1].get_text())
        maidens = _safe_int(cells[2].get_text())
        runs_conceded = _safe_int(cells[3].get_text())

        # Wickets cell may have a nested <span> with the number
        wickets_text = cells[4].get_text()
        wickets = _safe_int(wickets_text)

        economy = _safe_float(cells[5].get_text())
        dot_balls = _safe_int(cells[6].get_text())
        wides = _safe_int(cells[7].get_text())
        no_balls = _safe_int(cells[8].get_text())

        logger.debug("[SCRAPER] Bowler: %s | O=%.1f M=%d R=%d W=%d Econ=%.2f Dots=%d", name, overs, maidens, runs_conceded, wickets, economy, dot_balls)

        entries.append(BowlingEntry(
            name=name,
            overs=overs,
            maidens=maidens,
            runs_conceded=runs_conceded,
            wickets=wickets,
            economy=economy,
            dot_balls=dot_balls,
            wides=wides,
            no_balls=no_balls,
        ))

    logger.debug("[SCRAPER] Parsed %d bowlers from table", len(entries))
    return entries


# ── Did Not Bat ────────────────────────────────────────────────────────────────

def _parse_did_not_bat(batting_table: ElementWrapper) -> list[str]:
    """Extract players listed under 'Did not bat' from the batting table footer."""
    if batting_table is None:
        return []

    dnb_players: list[str] = []
    # Find all rows, look for "Did not bat" section
    all_rows = batting_table.tag.find_all("tr") if batting_table.tag else []
    for row_tag in all_rows:
        row = ElementWrapper(row_tag)
        # Check if this row contains "Did not bat"
        spans = row.find_all("span.ds-text-overline-2")
        is_dnb_row = any("did not bat" in s.get_text().lower() for s in spans)
        if is_dnb_row:
            links = row.find_all("a[href*='/cricketers/']")
            for link in links:
                name = _clean_player_name(link.get_text())
                if name:
                    dnb_players.append(name)
            break

    return dnb_players


# ── Dismissal Parsing ──────────────────────────────────────────────────────────

def _parse_dismissal(batter_name: str, dismissal_text: str) -> DismissalDetail:
    """Parse a dismissal string into a DismissalDetail."""
    text = dismissal_text.strip()

    if not text or "not out" in text.lower():
        return DismissalDetail(
            batter_name=batter_name,
            dismissal_type="not_out",
        )

    # "c FielderName b BowlerName"  or  "c †FielderName b BowlerName"
    caught_match = re.match(
        r"c\s+[†]?(.+?)\s+b\s+(.+)", text, re.IGNORECASE
    )
    if caught_match:
        fielder = _clean_player_name(caught_match.group(1))
        bowler = _clean_player_name(caught_match.group(2))
        return DismissalDetail(
            batter_name=batter_name,
            dismissal_type="caught",
            bowler_name=bowler,
            fielder_name=fielder,
        )

    # "c & b BowlerName" (caught and bowled)
    cnb_match = re.match(r"c\s*&\s*b\s+(.+)", text, re.IGNORECASE)
    if cnb_match:
        bowler = _clean_player_name(cnb_match.group(1))
        return DismissalDetail(
            batter_name=batter_name,
            dismissal_type="caught",
            bowler_name=bowler,
            fielder_name=bowler,  # bowler is also the fielder
        )

    # "lbw b BowlerName"
    lbw_match = re.match(r"lbw\s+b\s+(.+)", text, re.IGNORECASE)
    if lbw_match:
        bowler = _clean_player_name(lbw_match.group(1))
        return DismissalDetail(
            batter_name=batter_name,
            dismissal_type="lbw",
            bowler_name=bowler,
        )

    # "b BowlerName" (bowled)
    bowled_match = re.match(r"^\s*b\s+(.+)", text, re.IGNORECASE)
    if bowled_match:
        bowler = _clean_player_name(bowled_match.group(1))
        return DismissalDetail(
            batter_name=batter_name,
            dismissal_type="bowled",
            bowler_name=bowler,
        )

    # "st †FielderName b BowlerName"
    stumped_match = re.match(
        r"st\s+[†]?(.+?)\s+b\s+(.+)", text, re.IGNORECASE
    )
    if stumped_match:
        fielder = _clean_player_name(stumped_match.group(1))
        bowler = _clean_player_name(stumped_match.group(2))
        return DismissalDetail(
            batter_name=batter_name,
            dismissal_type="stumped",
            bowler_name=bowler,
            fielder_name=fielder,
        )

    # "run out (FielderName)" — direct
    ro_direct_match = re.match(
        r"run\s+out\s+\(([^/]+)\)", text, re.IGNORECASE
    )
    if ro_direct_match:
        fielder = _clean_player_name(ro_direct_match.group(1))
        return DismissalDetail(
            batter_name=batter_name,
            dismissal_type="run_out",
            fielder_name=fielder,
            is_direct_run_out=True,
        )

    # "run out (Fielder1/Fielder2)" — indirect (multiple players)
    ro_indirect_match = re.match(
        r"run\s+out\s+\((.+?)/(.+?)\)", text, re.IGNORECASE
    )
    if ro_indirect_match:
        fielder1 = _clean_player_name(ro_indirect_match.group(1))
        fielder2 = _clean_player_name(ro_indirect_match.group(2))
        # Both fielders get credit; we store the first as primary
        return DismissalDetail(
            batter_name=batter_name,
            dismissal_type="run_out",
            fielder_name=f"{fielder1}/{fielder2}",
            is_direct_run_out=False,
        )

    # "hit wicket b BowlerName"
    hw_match = re.match(r"hit\s+wicket\s+b\s+(.+)", text, re.IGNORECASE)
    if hw_match:
        bowler = _clean_player_name(hw_match.group(1))
        return DismissalDetail(
            batter_name=batter_name,
            dismissal_type="hit_wicket",
            bowler_name=bowler,
        )

    # Fallback — unknown dismissal
    logger.warning("Unknown dismissal format for %s: '%s'", batter_name, text)
    return DismissalDetail(
        batter_name=batter_name,
        dismissal_type="unknown",
    )


# ── Fielding Derivation ───────────────────────────────────────────────────────

def _derive_fielding(dismissals: list[DismissalDetail]) -> list[FieldingEntry]:
    """Aggregate fielding contributions from all dismissals in an innings."""
    fielding_map: dict[str, FieldingEntry] = {}

    for d in dismissals:
        if d.dismissal_type == "caught" and d.fielder_name:
            entry = fielding_map.setdefault(
                d.fielder_name, FieldingEntry(name=d.fielder_name)
            )
            entry.catches += 1

        elif d.dismissal_type == "stumped" and d.fielder_name:
            entry = fielding_map.setdefault(
                d.fielder_name, FieldingEntry(name=d.fielder_name)
            )
            entry.stumpings += 1

        elif d.dismissal_type == "run_out" and d.fielder_name:
            if d.is_direct_run_out:
                entry = fielding_map.setdefault(
                    d.fielder_name, FieldingEntry(name=d.fielder_name)
                )
                entry.run_out_direct += 1
            else:
                # Multiple fielders involved — split by "/"
                fielders = d.fielder_name.split("/")
                for f in fielders:
                    f = f.strip()
                    entry = fielding_map.setdefault(
                        f, FieldingEntry(name=f)
                    )
                    entry.run_out_indirect += 1

    return list(fielding_map.values())


# ── Name Resolution ───────────────────────────────────────────────────────────

def _resolve_short_names(innings_list: list[InningsData]) -> None:
    """
    Resolve short names (e.g. 'Klaasen') in dismissals and fielding entries
    to full names (e.g. 'Heinrich Klaasen') using all known player names
    from batting + bowling across all innings.

    Mutates the innings objects in-place.
    """
    # Build a set of all known full names from batting and bowling
    full_names: set[str] = set()
    for inn in innings_list:
        for b in inn.batting:
            full_names.add(b.name)
        for b in inn.bowling:
            full_names.add(b.name)

    # Build last-name → full-name mapping
    # If multiple players share a last name, skip (ambiguous)
    last_name_map: dict[str, str] = {}
    last_name_conflicts: set[str] = set()
    for full in full_names:
        parts = full.split()
        if len(parts) >= 2:
            last = parts[-1].lower()
            if last in last_name_map and last_name_map[last] != full:
                last_name_conflicts.add(last)
            else:
                last_name_map[last] = full
        # Also map on just the name itself (single-word names)
        last_name_map[full.lower()] = full

    # Remove conflicting last names
    for conflict in last_name_conflicts:
        del last_name_map[conflict]

    def resolve(name: str) -> str:
        if not name:
            return name
        if name in full_names:
            return name
        key = name.strip().lower()
        return last_name_map.get(key, name)

    resolved_count = 0

    for inn in innings_list:
        # Resolve dismissal fielder/bowler names
        for d in inn.dismissals:
            if d.fielder_name:
                # Handle compound "Fielder1/Fielder2" for indirect run-outs
                if "/" in d.fielder_name:
                    parts = d.fielder_name.split("/")
                    resolved_parts = [resolve(p.strip()) for p in parts]
                    new_name = "/".join(resolved_parts)
                    if new_name != d.fielder_name:
                        logger.debug("[RESOLVE] fielder '%s' → '%s'", d.fielder_name, new_name)
                        resolved_count += 1
                    d.fielder_name = new_name
                else:
                    new_name = resolve(d.fielder_name)
                    if new_name != d.fielder_name:
                        logger.debug("[RESOLVE] fielder '%s' → '%s'", d.fielder_name, new_name)
                        resolved_count += 1
                    d.fielder_name = new_name
            if d.bowler_name:
                new_name = resolve(d.bowler_name)
                if new_name != d.bowler_name:
                    logger.debug("[RESOLVE] bowler '%s' → '%s'", d.bowler_name, new_name)
                    resolved_count += 1
                d.bowler_name = new_name

        # Rebuild fielding from the resolved dismissals
        inn.fielding = _derive_fielding(inn.dismissals)

    logger.info("[RESOLVE] Resolved %d short names across all innings", resolved_count)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_match_id(url: str) -> str:
    """Extract the numeric match ID from an ESPNcricinfo URL.

    The URL format is: .../series/<series-slug>-<series_id>/<match-slug>-<match_id>/full-scorecard
    We want the *last* numeric ID in the path (the match ID, not the series ID).
    """
    matches = re.findall(r"-(\d{5,})(?=/|$)", url)
    if matches:
        return matches[-1]  # last numeric ID = match ID
    return "unknown"


def _extract_venue_date(title: str) -> tuple[str, str]:
    """Best-effort extraction of venue and date from the page title."""
    # Typical: "RR vs SRH Cricket Scorecard, 36th Match at Jaipur, April 25, 2026"
    venue = ""
    date = ""
    at_match = re.search(r"at\s+(.+?)(?:,\s*(.+))?$", title)
    if at_match:
        venue = at_match.group(1).strip().rstrip(",")
        date = at_match.group(2).strip() if at_match.group(2) else ""
    return venue, date


def _clean_player_name(raw: str) -> str:
    """Strip special chars like (c), †, &nbsp;, commas from player names."""
    name = raw.strip()
    # Remove (c) captain indicator and † wicketkeeper indicator
    name = re.sub(r"\(c\)", "", name)
    name = re.sub(r"[†]", "", name)
    # Remove trailing comma, nbsp, whitespace
    name = name.replace("\xa0", " ").replace(",", "").strip()
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name)
    return name


def _safe_int(text: str) -> int:
    """Convert text to int, returning 0 on failure."""
    try:
        return int(re.sub(r"[^\d-]", "", text))
    except (ValueError, TypeError):
        return 0


def _safe_float(text: str) -> float:
    """Convert text to float, returning 0.0 on failure."""
    try:
        cleaned = re.sub(r"[^\d.\-]", "", text)
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0
