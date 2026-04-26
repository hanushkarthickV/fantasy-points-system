"""
Centralised CSS selectors for ESPNcricinfo scorecard pages.
All selectors live here so that changes in site structure only require edits in one place.
"""

# ── Match Header ───────────────────────────────────────────────────────────────
MATCH_TITLE = "h1"
MATCH_RESULT = "p.ds-text-body-1.ds-font-medium.ds-truncate span span"

# ── Innings Containers ─────────────────────────────────────────────────────────
# Each innings is inside a div with class ds-mb-4 that contains the team header
INNINGS_CONTAINER = "div.ds-mb-4.ds-border-t"
INNINGS_TEAM_NAME = "span.ds-text-title-1"

# ── Batting Table ──────────────────────────────────────────────────────────────
BATTING_TABLE = "table.ci-scorecard-table"
BATTING_TBODY = "table.ci-scorecard-table > tbody"
BATTING_ROW = "table.ci-scorecard-table > tbody > tr"
BATTER_NAME_LINK = "a[href*='/cricketers/']"

# ── Bowling Table ──────────────────────────────────────────────────────────────
# The bowling table follows the batting table; it does NOT have ci-scorecard-table
BOWLING_TABLE_HEADER = "th"  # first <th> text = "Bowling"
BOWLING_TBODY = "tbody"

# ── Did Not Bat ────────────────────────────────────────────────────────────────
DNB_SECTION_HEADER = "span.ds-text-overline-2"  # text "Did not bat"
DNB_PLAYER_LINK = "a[href*='/cricketers/']"

# ── Fall of Wickets ────────────────────────────────────────────────────────────
FOW_SECTION_HEADER = "span.ds-text-overline-2"  # text "Fall of wickets"

# ── Team Score (from header) ───────────────────────────────────────────────────
TEAM_SCORE_ROW = "div.ci-team-score"
TEAM_NAME_LINK = "div.ci-team-score a[href*='/team/'] span"
TEAM_SCORE_VALUE = "div.ci-team-score div.ds-text-header-5 span:last-child"

# ── Not-out indicator ──────────────────────────────────────────────────────────
NOTOUT_CLASS = "ci-v2-scorecard-player-notout"
