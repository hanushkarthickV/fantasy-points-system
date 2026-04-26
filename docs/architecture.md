# Architecture

## Overview

The Fantasy Points System is a full-stack application built with a **FastAPI** backend and **React** frontend. It follows a layered architecture with clear separation of concerns.

## Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│   Components → API Service → Types                      │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP/JSON
┌─────────────────────▼───────────────────────────────────┐
│                  API Layer (FastAPI)                     │
│   routes.py — request validation, error handling        │
├─────────────────────────────────────────────────────────┤
│               Service Layer (Orchestration)              │
│   match_service.py — workflow coordination              │
│   sheet_service.py — Google Sheets + fuzzy matching     │
├─────────────────────────────────────────────────────────┤
│                Domain / Engine Layer                     │
│   points_calculator.py — pure scoring functions         │
│   scorecard_scraper.py — HTML parsing logic             │
├─────────────────────────────────────────────────────────┤
│                  Wrapper Layer                           │
│   browser_wrapper.py — Selenium abstraction             │
│   element_wrapper.py — BeautifulSoup abstraction        │
│   sheet_wrapper.py   — gspread abstraction              │
├─────────────────────────────────────────────────────────┤
│                  Infrastructure                         │
│   config.py — centralized settings                      │
│   logger.py — logging setup                             │
│   models/schemas.py — Pydantic data models              │
└─────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Wrapper Pattern
All external libraries (Selenium, BeautifulSoup, gspread) are wrapped in dedicated classes. This:
- Makes unit testing possible with mocks
- Isolates third-party API changes to a single file
- Provides a domain-specific API

### 2. Pure Calculation Engine
`points_calculator.py` is entirely stateless. Given a `MatchMetadata` object, it deterministically produces `MatchPoints`. No I/O, no side effects. This makes it:
- Easy to test
- Easy to extend (add ODI, Test formats)
- Safe to call repeatedly

### 3. JSON Persistence
Every step saves its output as JSON under `data/matches/<match_id>/`:
- `metadata.json` — raw scraped data
- `points.json` — calculated points
- `update_result.json` — sheet update diff

This enables:
- Debugging by inspecting intermediate data
- Replaying any step without re-running previous steps
- Audit trail of all changes

### 4. Human-in-the-Loop
The frontend enforces a step-wise workflow where the user must explicitly approve:
1. Scraped data before calculating points
2. Calculated points before updating the sheet

This prevents accidental data corruption from bad scrapes.

### 5. Name Resolution
ESPN Cricinfo dismissal text uses short names ("Klaasen") while player links have full names ("Heinrich Klaasen"). The `_resolve_short_names()` function builds a last-name → full-name mapping and resolves all references post-parse.

## Data Flow

```
URL → Scraper → MatchMetadata → Calculator → MatchPoints → SheetService → Google Sheets
         │              │              │              │              │
         ▼              ▼              ▼              ▼              ▼
     Browser        metadata.json  Pure func     points.json   update_result.json
     (Selenium)                    (no I/O)
```
