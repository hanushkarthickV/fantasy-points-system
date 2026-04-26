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
GOOGLE_CREDENTIALS_PATH = CREDENTIALS_DIR / "google_service_account.json"
SPREADSHEET_ID = "1VP_iSR_LoJRyyGWENSuc8gKz1YbphD0htKd-w66mvFI"
WORKSHEET_NAME = "IPL_2026_Auction_List"
PLAYER_NAME_COLUMN = "Player Name"
POINTS_COLUMN = "DreamPoints"
SPECIALISM_COLUMN = "Specialism"

# ── Fuzzy Matching ─────────────────────────────────────────────────────────────
FUZZY_AUTO_MATCH_THRESHOLD = 80
FUZZY_REVIEW_THRESHOLD = 60

# ── Selenium ───────────────────────────────────────────────────────────────────
BROWSER_HEADLESS = True
PAGE_LOAD_TIMEOUT = 30
ELEMENT_WAIT_TIMEOUT = 15
