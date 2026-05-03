# Fantasy Points System — Functional Overview

A detailed guide to how the system works end-to-end: statuses, background
jobs, discovery, extraction, and the complete data flow.

---

## 1. System Purpose

Automates IPL fantasy-points calculation by scraping scorecards from
ESPNcricinfo, computing points per player using custom scoring rules, and
pushing the results to a shared Google Sheet.

---

## 2. High-Level Flow

```
ESPN Schedule Page ──► Match Discovery ──► Match Listing (Frontend)
                                                │
                                    User clicks "Extract"
                                                │
                                                ▼
                                     Extraction Queue (DB)
                                                │
                                    Background Worker picks job
                                                │
                                    ┌───────────┴───────────┐
                                    │ 1. Selenium scrape     │
                                    │ 2. Points calculation  │
                                    └───────────┬───────────┘
                                                │
                                                ▼
                                     Points Review (Frontend)
                                                │
                                    User approves / edits
                                                │
                                                ▼
                                     Google Sheets Update
```

---

## 3. Match Statuses

Every match row has a `status` field that drives the UI and backend logic.

| Status                | Meaning                                              | UI Action Available           |
|-----------------------|------------------------------------------------------|-------------------------------|
| `scheduled`           | Match discovered but not yet played                  | Disabled — "Awaiting result"  |
| `completed`           | Match played, scorecard link available                | **Extract** button            |
| `queued`              | Extraction request in the queue                      | Spinner — waiting             |
| `extracting`          | Worker is actively scraping + calculating            | Spinner — in progress         |
| `points_calculated`   | Scrape + calculation done, awaiting user review      | **Review Points** button      |
| `sheet_updated`       | Points pushed to Google Sheet                        | **History** button (read-only)|
| `extraction_failed`   | Scrape or calculation error                          | **Extract** (retry)           |
| `manually_extracted`  | Matches 1–42 (pre-V2, processed via V1)              | **Re-extract** button         |

### Status Transition Diagram

```
                         ┌──────────────────────────────────────┐
                         │                                      │
   SCHEDULED ──► COMPLETED ──► QUEUED ──► EXTRACTING ──► POINTS_CALCULATED ──► SHEET_UPDATED
                     ▲              │                  │
                     │              │                  │
                     │              ▼                  ▼
                     └──── EXTRACTION_FAILED ──────────┘
                                (user retries)

   MANUALLY_EXTRACTED ──► QUEUED ──► EXTRACTING ──► SHEET_UPDATED (skip review)
```

### Key Rules

- **SCHEDULED → COMPLETED**: Happens during "Sync Matches" when ESPN adds a
  scorecard link for the match.
- **Re-extract for manually_extracted / sheet_updated**: Sets a `skip_review`
  flag so the worker automatically sets the final status to `sheet_updated`
  (bypassing the review screen, since these matches were already pushed to
  the sheet).
- **Scheduled matches are filtered to today only** (IST timezone) in the
  match listing to keep the UI focused.

---

## 4. Match Discovery ("Sync Matches")

**Triggered by**: User clicks the "Sync Matches" button on the frontend.

**What it does**:

1. Fetches the ESPN IPL 2026 schedule page:
   `https://www.espncricinfo.com/series/ipl-2026-1510719/match-schedule-fixtures-and-results`
2. Parses HTML with regex to find two types of links:
   - `/full-scorecard` links → match is **completed**
   - `/live-cricket-score` links → match is **scheduled** (ongoing or upcoming)
3. Extracts from each URL slug:
   - ESPN match ID (7-digit number)
   - Match number (e.g. "43rd Match" → 43)
   - Team names (e.g. "rajasthan-royals-vs-delhi-capitals")
4. Upserts into the `matches` table:
   - **New match**: Inserted with appropriate status (`completed` or `scheduled`; matches 1–42 get `manually_extracted`)
   - **Existing match**: If status is `scheduled` and now has a scorecard → transitions to `completed`
5. Persists `last_sync_time` in the `app_config` table (displayed on frontend).

**File**: `backend/scheduler/match_discovery.py`

**Note**: There is no automatic scheduler. Discovery is entirely manual, triggered by the user.

---

## 5. Extraction Queue & Background Worker

### Queue Table (`extraction_queue`)

| Column         | Description                                              |
|----------------|----------------------------------------------------------|
| `id`           | Auto-increment primary key                               |
| `match_id`     | FK to `matches.id`                                       |
| `status`       | `pending` → `processing` → `done` / `failed`            |
| `skip_review`  | Boolean — if true, worker sets match to `sheet_updated`  |
| `error_message`| Error details on failure                                 |
| `created_at`   | Timestamp when job was queued                            |
| `started_at`   | Timestamp when worker started processing                 |
| `completed_at` | Timestamp when processing finished                       |

### Background Worker

The worker runs as a **daemon thread** inside the same Uvicorn process.
No external job runner (Celery, APScheduler, etc.) is needed.

**Lifecycle**:
- Starts automatically on application startup (`backend/main.py` lifespan)
- Polls the `extraction_queue` table every **3 seconds**
- Processes **one job at a time** (Selenium is resource-heavy)
- Stops gracefully on server shutdown

**Processing Steps** (per job):

1. Pick the oldest `pending` job from the queue
2. Mark job as `processing`, match as `extracting`
3. **Scrape scorecard** via Selenium (headless Chrome):
   - Navigate to the ESPN full-scorecard URL
   - Extract batting, bowling, fielding data, dismissals, playing XI
   - Parse venue, date, result text from the page
4. Store scraped `MatchMetadata` as JSON in `matches.metadata_json`
5. **Calculate fantasy points** using the scoring engine:
   - Batting, bowling, fielding points per player
   - Playing XI bonus (+4 points for every player)
   - Bowler identification via Google Sheet lookup
6. Store `MatchPoints` as JSON in `matches.points_json`
7. Set final match status:
   - If `skip_review=True` → `sheet_updated` (match was previously processed)
   - Otherwise → `points_calculated` (user needs to review)
8. Mark job as `done`

**On failure**: Match status → `extraction_failed`, job status → `failed`,
error message stored for debugging.

**File**: `backend/services/extraction_worker.py`

---

## 6. Points Calculation Engine

**File**: `backend/engine/points_calculator.py`

Takes scraped `MatchMetadata` and produces `MatchPoints` containing a
`PlayerPoints` entry for every player in the match.

### Scoring Categories

| Category          | Examples                                               |
|-------------------|--------------------------------------------------------|
| **Batting**       | Runs scored, boundaries, strike rate, milestones       |
| **Bowling**       | Wickets, economy, maidens, milestones                  |
| **Fielding**      | Catches, stumpings, run-outs, direct hits              |
| **Playing XI**    | +4 bonus for every player in the match                 |

Full scoring rules are in `docs/scoring-rules.md`.

### Bowler Identification

The calculator accepts an optional `bowler_names` set (fetched from the
Google Sheet's bowler column). This is used to differentiate all-rounders
from pure batters for certain bonus rules.

---

## 7. Google Sheets Integration

**File**: `backend/services/sheet_service.py`

### Update Flow

1. User clicks "Approve & Update Spreadsheet" on the review screen
2. Backend reads the master sheet via `gspread`
3. For each player with calculated points:
   - **Fuzzy match** the player name against the sheet's player column
     (using `rapidfuzz`, threshold: 80%)
   - If matched → update the points cell in the correct match column
   - If not matched → add to `unmatched` list
4. Return `SheetUpdateResponse` with:
   - `matched`: Players successfully updated (with match % score)
   - `unmatched`: Players that couldn't be matched (with best guess)
5. Results stored in `matches.sheet_update_json` for later viewing

### Retry Unmatched Players

If players are unmatched, the user can:
1. See the unmatched list with best-guess suggestions
2. Type the correct sheet name for each player
3. Click "Retry" → backend calls `update_specific_players` with corrections
4. Merged results update `sheet_update_json`

---

## 8. Frontend Pages

### Match Listing (`MatchesPage.tsx`)

The main page showing all matches with:
- **Status badges** (color-coded per status)
- **Metadata** (venue, date/time, result text)
- **Action buttons** based on status (Extract / Review / History / disabled)
- **Last sync time** display
- **Sync Matches** button for manual discovery
- **Refresh** button to reload the list
- **Auto-polling** every 5s when any match is in `queued`/`extracting` state

**Filtering**:
- All non-scheduled matches are always shown
- Scheduled matches are filtered to **today only** (IST timezone)

### Review/History Overlay

- **Review mode** (`points_calculated`): Full points table with expand/collapse per player, inline editing, "Approve & Update Spreadsheet" button, sheet results panel with retry for unmatched
- **History mode** (`sheet_updated` / `manually_extracted` after re-extract): Read-only view of points — no approve button, no editing

---

## 9. API Endpoints

| Method | Path                                  | Description                                         |
|--------|---------------------------------------|-----------------------------------------------------|
| GET    | `/api/v2/matches`                     | List matches (scheduled filtered to today IST)      |
| POST   | `/api/v2/matches/{id}/queue-extract`  | Queue extraction (sets skip_review for re-extracts) |
| GET    | `/api/v2/matches/{id}/points`         | Get calculated points JSON                          |
| POST   | `/api/v2/matches/{id}/update-sheet`   | Push points to Google Sheet                         |
| GET    | `/api/v2/matches/{id}/sheet-result`   | Get stored sheet update result                      |
| PATCH  | `/api/v2/matches/{id}/edit-players`   | Edit player names/points                            |
| POST   | `/api/v2/matches/{id}/retry-unmatched`| Retry sheet update for unmatched players             |
| POST   | `/api/v2/sync-matches`               | Manual match discovery from ESPN                     |
| GET    | `/api/v2/queue/status`               | Queue health (pending/processing counts)             |
| POST   | `/api/v2/auth/signup`                | Register new user                                    |
| POST   | `/api/v2/auth/login`                 | Login, returns JWT                                   |
| GET    | `/health`                            | Health check                                         |

---

## 10. Background Processes Summary

| Process            | Type            | Trigger                  | Frequency        |
|--------------------|-----------------|--------------------------|------------------|
| Extraction Worker  | Daemon thread   | Auto-start on app boot   | Polls every 3s   |
| Match Discovery    | Manual          | User clicks Sync         | On-demand        |

There are **no scheduled/cron jobs**. All operations are either user-triggered
or driven by the extraction worker polling the queue.

---

## 11. Database Tables Summary

| Table              | Purpose                                                  |
|--------------------|----------------------------------------------------------|
| `matches`          | One row per IPL match — status, metadata, points, sheet results |
| `extraction_queue` | Job queue for async extraction processing                |
| `extractions`      | Audit log of every extraction attempt                    |
| `app_config`       | Key-value store (e.g. `last_sync_time`)                  |
| `users`            | Authentication (email + hashed password)                 |

---

## 12. Deployment

- **Platform**: Render (free tier, Docker-based)
- **Database**: Supabase PostgreSQL (connection pooler URL, port 6543)
- **Remote**: `github` remote only (Render auto-deploys from `version-2` branch)
- **Build**: Docker (`./Dockerfile` at repo root)
- **Environment variables**: `DATABASE_URL`, `JWT_SECRET` set in Render dashboard

See `docs/DEPLOYMENT.md` for full setup instructions.
