# Fantasy Points System

> Automated T20 cricket fantasy-points calculator that scrapes ESPN Cricinfo scorecards, computes fantasy points using a comprehensive T20 scoring algorithm, and updates a Google Sheets auction list via fuzzy player-name matching.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [Running with Docker](#running-with-docker)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Data Storage](#data-storage)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Scorecard Scraping** — Headless Chrome (Selenium) scrapes full scorecards from ESPN Cricinfo, extracting batting, bowling, and fielding data.
- **Smart Name Resolution** — Short names from dismissal text (e.g. "Klaasen") are automatically resolved to full names (e.g. "Heinrich Klaasen").
- **T20 Fantasy Points Engine** — Complete implementation of the T20 scoring system including batting milestones, bowling bonuses, fielding points, and penalties.
- **Fuzzy Player Matching** — Uses `thefuzz` to match scraped names against a Google Sheets auction list with configurable thresholds.
- **Cumulative Google Sheets Updates** — Adds match points to existing totals, preserving historical data.
- **Step-wise UI** — React frontend with a human-in-the-loop workflow: Scrape → Review Scorecard → Review Points → Update Sheet.
- **Centralized Logging** — Rotating file + console logging with module-level granularity.

---

## Architecture

```
┌──────────────┐     HTTP/JSON     ┌──────────────────────────────────────┐
│  React SPA   │◄────────────────►│  FastAPI Backend (port 8080)         │
│  (port 5173) │                  │                                      │
└──────────────┘                  │  ┌──────────┐  ┌──────────────────┐  │
                                  │  │ Scraper   │  │ Points Engine    │  │
                                  │  │ (Selenium)│  │ (Pure Functions) │  │
                                  │  └─────┬─────┘  └────────┬─────────┘  │
                                  │        │                 │            │
                                  │  ┌─────▼─────────────────▼─────────┐  │
                                  │  │     Match Service (Orchestrator) │  │
                                  │  └─────────────┬───────────────────┘  │
                                  │                │                      │
                                  │  ┌─────────────▼───────────────────┐  │
                                  │  │  Sheet Service (gspread + fuzzy) │  │
                                  │  └─────────────────────────────────┘  │
                                  └──────────────────────────────────────┘
                                               │
                                               ▼
                                  ┌──────────────────────┐
                                  │   Google Sheets API   │
                                  └──────────────────────┘
```

---

## Project Structure

```
Fantasy Points System/
├── backend/
│   ├── api/
│   │   └── routes.py              # FastAPI route definitions
│   ├── engine/
│   │   └── points_calculator.py   # T20 fantasy scoring algorithm
│   ├── models/
│   │   └── schemas.py             # Pydantic data models
│   ├── scraper/
│   │   ├── scorecard_scraper.py   # ESPN Cricinfo scraper + parser
│   │   └── selectors.py           # CSS selectors (centralized)
│   ├── services/
│   │   ├── match_service.py       # Workflow orchestrator
│   │   └── sheet_service.py       # Google Sheets read/write + fuzzy matching
│   ├── wrappers/
│   │   ├── browser_wrapper.py     # Selenium WebDriver abstraction
│   │   ├── element_wrapper.py     # BeautifulSoup abstraction
│   │   └── sheet_wrapper.py       # gspread abstraction
│   ├── config.py                  # Centralized configuration
│   ├── logger.py                  # Centralized logging setup
│   ├── main.py                    # FastAPI app entry point
│   └── requirements.txt           # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/            # React UI components
│   │   ├── services/api.ts        # Axios API client
│   │   ├── types/index.ts         # TypeScript type definitions
│   │   ├── App.tsx                # Main application component
│   │   └── main.tsx               # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── credentials/                   # Google service account JSON (gitignored)
├── data/
│   ├── matches/<match_id>/        # Per-match JSON artifacts
│   │   ├── metadata.json
│   │   ├── points.json
│   │   └── update_result.json
│   └── logs/                      # Rotating application logs
├── docs/                          # Project documentation
├── .github/workflows/             # CI/CD pipelines
├── docker-compose.yml
├── Dockerfile
├── .gitignore
├── .editorconfig
├── .env.example
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

---

## Prerequisites

| Tool            | Version  | Notes                            |
| --------------- | -------- | -------------------------------- |
| Python          | ≥ 3.11   |                                  |
| Node.js         | ≥ 16     | v18+ recommended                 |
| Google Chrome   | Latest   | Required for Selenium scraping   |
| ChromeDriver    | Auto     | Managed by `webdriver-manager`   |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/fantasy-points-system.git
cd fantasy-points-system
```

### 2. Backend setup

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r backend/requirements.txt
```

### 3. Frontend setup

```bash
cd frontend
npm install
cd ..
```

### 4. Google Sheets credentials

1. Go to [Google Cloud Console → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Create a service account (or use an existing one)
3. Create a JSON key and download it
4. Save it as `credentials/google_service_account.json`
5. **Share your Google Sheet** with the service account email as **Editor**

---

## Configuration

All backend config lives in `backend/config.py`:

| Setting                    | Default                  | Description                        |
| -------------------------- | ------------------------ | ---------------------------------- |
| `SPREADSHEET_ID`           | *(your sheet ID)*        | Google Sheets document ID          |
| `WORKSHEET_NAME`           | `IPL_2026_Auction_List`  | Tab/worksheet name                 |
| `PLAYER_NAME_COLUMN`       | `Player Name`            | Column header for player names     |
| `POINTS_COLUMN`            | `DreamPoints`            | Column header for points           |
| `SPECIALISM_COLUMN`        | `Specialism`             | Column header for player role      |
| `FUZZY_AUTO_MATCH_THRESHOLD` | `80`                   | Auto-match threshold (0–100)       |
| `BROWSER_HEADLESS`         | `True`                   | Run Chrome headless                |
| `PAGE_LOAD_TIMEOUT`        | `30`                     | Selenium page load timeout (sec)   |
| `ELEMENT_WAIT_TIMEOUT`     | `15`                     | Selenium element wait timeout (sec)|

---

## Running Locally

### Start the backend

```bash
# From project root, with venv activated
uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload
```

### Start the frontend

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

### Workflow

1. Paste an ESPN Cricinfo full-scorecard URL
2. Review the scraped scorecard data → Approve
3. Review calculated fantasy points → Approve
4. Points are written to the Google Sheet

---

## Running with Docker

```bash
# Build and start both services
docker-compose up --build

# Or run in background
docker-compose up --build -d
```

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8080
- **API Docs**: http://localhost:8080/docs

---

## API Reference

| Method | Endpoint                        | Description                          |
| ------ | ------------------------------- | ------------------------------------ |
| POST   | `/api/scrape`                   | Scrape a scorecard from URL          |
| POST   | `/api/calculate-points`         | Calculate fantasy points             |
| POST   | `/api/update-sheet`             | Push points to Google Sheets         |
| GET    | `/api/match/{id}/metadata`      | Read persisted match metadata        |
| GET    | `/api/match/{id}/points`        | Read persisted match points          |
| GET    | `/health`                       | Health check                         |

Interactive API documentation is available at **http://localhost:8080/docs** (Swagger UI).

### Example: Full workflow via cURL

```bash
# Step 1: Scrape
curl -X POST http://localhost:8080/api/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.espncricinfo.com/series/ipl-2026-1510719/rajasthan-royals-vs-sunrisers-hyderabad-36th-match-1529279/full-scorecard"}'

# Step 2: Calculate points (use match_id from step 1)
curl -X POST http://localhost:8080/api/calculate-points \
  -H "Content-Type: application/json" \
  -d '{"match_id": "1529279"}'

# Step 3: Update sheet
curl -X POST http://localhost:8080/api/update-sheet \
  -H "Content-Type: application/json" \
  -d '{"match_id": "1529279"}'
```

---

## Testing

### Run the API integration test

```bash
# With venv activated and backend running
python test_api.py all
```

### Run individual steps

```bash
python test_api.py scrape
python test_api.py points <match_id>
python test_api.py sheet <match_id>
```

---

## Data Storage

Match data is stored under `data/matches/<match_id>/`:

```
data/
├── matches/
│   └── 1529279/                    # RR vs SRH, 36th Match
│       ├── metadata.json           # Scraped scorecard data
│       ├── points.json             # Calculated fantasy points
│       └── update_result.json      # Sheet update diff
└── logs/
    └── app.log                     # Rotating log (5MB × 3 backups)
```

Each match gets its own directory, making it easy to inspect, debug, or replay any step.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Development setup
- Code style and conventions
- Pull request process
- Branching strategy

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
