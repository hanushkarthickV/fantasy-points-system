# Fantasy Points System — V2 Architecture

## Overview

Version 2 replaces the manual URL-input flow with a fully integrated match listing,
async extraction queue, points review, and sheet update workflow backed by PostgreSQL.

---

## Tech Stack

| Layer      | Technology                                                   |
|------------|--------------------------------------------------------------|
| Frontend   | React 18 + Vite + Tailwind CSS + Lucide icons               |
| Backend    | FastAPI + SQLAlchemy ORM + Uvicorn                           |
| Database   | PostgreSQL on Supabase (free tier, 500 MB)                   |
| Scraping   | Selenium (headless Chrome) + BeautifulSoup4                  |
| Sheets     | gspread + Google Service Account                             |
| Auth       | JWT (email + password)                                       |
| Deployment | Render free tier (single web service)                        |

---

## Database Schema

### `matches`
| Column             | Type        | Description                                   |
|--------------------|-------------|-----------------------------------------------|
| id                 | int PK      | Auto-increment                                |
| espn_match_id      | varchar(32) | ESPN unique match ID (e.g. `1529286`)         |
| match_number       | int         | Match number in the IPL season                |
| title              | varchar     | E.g. "Rajasthan Royals Vs Delhi Capitals ..." |
| team1, team2       | varchar     | Team names                                    |
| venue              | varchar     | Ground name                                   |
| match_date         | datetime    | Scheduled date/time                           |
| scorecard_url      | text        | Full ESPN scorecard URL                        |
| status             | varchar(32) | See [Match Status Flow](#match-status-flow)    |
| result_text        | text        | "RR won by 8 wickets" etc.                    |
| metadata_json      | jsonb       | Full `MatchMetadata` after extraction          |
| points_json        | jsonb       | Calculated `MatchPoints`                       |
| sheet_update_json  | jsonb       | Last `SheetUpdateResponse` (matched/unmatched) |
| discovered_at      | datetime    | When the match was first scraped from schedule |
| extracted_at       | datetime    | When scorecard extraction completed            |
| updated_at         | datetime    | Auto-updated on any change                     |

### `extraction_queue`
| Column         | Type        | Description                           |
|----------------|-------------|---------------------------------------|
| id             | int PK      | Auto-increment                        |
| match_id       | int FK      | References `matches.id`               |
| status         | varchar(32) | `pending` / `processing` / `done` / `failed` |
| error_message  | text        | Error details if failed               |
| skip_review    | boolean     | If true, worker sets match to `sheet_updated` directly |
| created_at     | datetime    | When queued                           |
| started_at     | datetime    | When worker picked it up              |
| completed_at   | datetime    | When processing finished              |

### `extractions` (audit log)
Tracks every extraction attempt for debugging.

### `users`
Simple email + hashed password for JWT auth.

---

## Match Status Flow

```
SCHEDULED → COMPLETED → QUEUED → EXTRACTING → POINTS_CALCULATED → SHEET_UPDATED
                  ↑                    |                                |
                  |                    ↓                                |
                  ←──── EXTRACTION_FAILED ──────────────────────────────┘

MANUALLY_EXTRACTED → QUEUED → EXTRACTING → SHEET_UPDATED (skip_review)
```

- **SCHEDULED**: Match discovered but not yet played. All actions disabled ("Awaiting result"). Only today's scheduled matches (IST) are shown in the listing.
- **COMPLETED**: Match played, scorecard available. User can click "Extract".
- **QUEUED**: Extraction request is in the queue waiting to be processed.
- **EXTRACTING**: Background worker is scraping + calculating points.
- **POINTS_CALCULATED**: Extraction done, points ready. User sees "Review Points" button.
- **SHEET_UPDATED**: Points pushed to Google Sheets. User sees "History" button (read-only).
- **EXTRACTION_FAILED**: Something went wrong. User can retry with "Extract".
- **MANUALLY_EXTRACTED**: Matches 1–42 (pre-V2, already processed via V1). Re-extracting these skips review and goes directly to `SHEET_UPDATED`.

---

## Extraction Queue (Async Worker)

Instead of blocking the API during extraction (which takes 15–30s due to Selenium),
we use a **background worker thread** that:

1. Polls the `extraction_queue` table every 3 seconds
2. Picks the oldest `pending` job
3. Runs Selenium scrape + points calculation
4. Updates the match row with results
5. Marks the job as `done` or `failed`

**Key behavior**:
- Users can queue multiple extractions simultaneously
- Jobs are processed **one at a time** (Selenium is resource-heavy)
- The frontend auto-polls match list every 5s when any job is active
- No APScheduler dependency — simple `threading.Thread`

---

## API Endpoints (V2)

| Method | Path                                | Description                      |
|--------|-------------------------------------|----------------------------------|
| GET    | `/api/v2/matches`                   | List matches (with status filter)|
| POST   | `/api/v2/matches/{id}/queue-extract`| Queue extraction for a match     |
| GET    | `/api/v2/matches/{id}/points`       | Get calculated points JSON       |
| POST   | `/api/v2/matches/{id}/update-sheet` | Push points to Google Sheets     |
| GET    | `/api/v2/matches/{id}/sheet-result` | Get stored sheet update result   |
| PATCH  | `/api/v2/matches/{id}/edit-players` | Edit player names/points         |
| POST   | `/api/v2/sync-matches`              | Manual match discovery from ESPN |
| GET    | `/api/v2/queue/status`              | Queue health (pending/processing)|
| POST   | `/api/v2/auth/signup`               | Register new user                |
| POST   | `/api/v2/auth/login`                | Login, returns JWT               |
| GET    | `/health`                           | Health check                     |

---

## Frontend Flow

1. **Login/Signup** → JWT stored in localStorage
2. **Match Listing** → All matches with status badges and action buttons
3. **Sync Matches** → Scrapes ESPN schedule page for new matches
4. **Extract** → Queues extraction, status updates automatically via polling
5. **Review Points** → Full-screen overlay with:
   - Player list sorted by points (expandable breakdowns)
   - Inline editing of player names and point overrides
   - "Approve & Update Spreadsheet" button
6. **Sheet Update Results** → Shows matched/unmatched players inline
   - User can fix unmatched players, save edits, and re-update
   - User manually clicks back arrow when done
7. **History** → Same view for previously completed matches

---

## Key V2 Changes (from V1)

1. **No APScheduler** — manual "Sync Matches" button only
2. **No separate "Calculate" step** — extraction automatically calculates points
3. **Async extraction queue** — multiple matches can be queued, processed one-by-one
4. **Review screen stays open** after sheet update — shows matched/unmatched results
5. **History button** — view points for any previously processed match
6. **Scheduled matches** — displayed but actions disabled with "Awaiting result" tooltip
7. **Skip review for re-extracts** — manually_extracted/sheet_updated matches go straight to history after re-extraction
8. **Today-only scheduled filter** — only today's scheduled matches (IST) appear in the listing
9. **Live match discovery** — sync detects both completed (`/full-scorecard`) and scheduled (`/live-cricket-score`) matches from ESPN

---

## Environment Variables

```env
DATABASE_URL=postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres
JWT_SECRET=your-secret-key
```
