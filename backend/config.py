import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CREDENTIALS_DIR = BASE_DIR / "credentials"
DATA_DIR.mkdir(exist_ok=True)
CREDENTIALS_DIR.mkdir(exist_ok=True)

# ── Google Sheets ──────────────────────────────────────────────────────────────
# Look for credentials in multiple locations (local dev → Render secret files)
_CRED_CANDIDATES = [
    CREDENTIALS_DIR / "google_service_account.json",        # local dev
    Path("/etc/secrets/google_service_account.json"),        # Render secret files
]
GOOGLE_CREDENTIALS_PATH = next(
    (p for p in _CRED_CANDIDATES if p.exists()),
    _CRED_CANDIDATES[0],  # fallback to local path (will error clearly at runtime)
)
SPREADSHEET_ID = "1DnFIQbXyFTrS-Ha8YdpF6XwshLCVOlXXKng934WAbK4"
WORKSHEET_NAME = "IPL_2026_Auction_List"
SUMMARY_WORKSHEET_NAME = "Summary-PointsTable"
SUMMARY_SORT_COLUMN = "Dream11 Points"
PLAYER_NAME_COLUMN = "Player Name"
POINTS_COLUMN = "DreamPoints"
SPECIALISM_COLUMN = "Specialism"

# ── Fuzzy Matching ─────────────────────────────────────────────────────────────
FUZZY_AUTO_MATCH_THRESHOLD = 80
FUZZY_REVIEW_THRESHOLD = 60

# ── Selenium ───────────────────────────────────────────────────────────────────
BROWSER_HEADLESS = True
PAGE_LOAD_TIMEOUT = 60
ELEMENT_WAIT_TIMEOUT = 20
SCRAPE_MAX_RETRIES = 3
