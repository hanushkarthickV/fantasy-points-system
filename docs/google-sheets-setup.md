# Google Sheets Setup Guide

## 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Google Sheets API** and **Google Drive API**

## 2. Create a Service Account

1. Navigate to **IAM & Admin → Service Accounts**
2. Click **Create Service Account**
3. Give it a descriptive name (e.g. `fantasy-points-bot`)
4. Skip optional permission steps
5. Click **Done**

## 3. Generate a JSON Key

1. Click on the created service account
2. Go to the **Keys** tab
3. Click **Add Key → Create new key → JSON**
4. Download the JSON file
5. Save it as `credentials/google_service_account.json` in the project root

## 4. Share Your Spreadsheet

1. Open your Google Sheet
2. Click the **Share** button
3. Add the service account email (from the JSON file's `client_email` field) as an **Editor**
4. Uncheck "Notify people" and click **Share**

## 5. Configure the Spreadsheet ID

The spreadsheet ID is in the URL:
```
https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit
```

Update `backend/config.py`:
```python
SPREADSHEET_ID = "your-spreadsheet-id-here"
```

## Required Sheet Structure

Your worksheet must have these column headers (names configurable in `config.py`):

| Column          | Purpose                            |
| --------------- | ---------------------------------- |
| `Player Name`   | Player full name for fuzzy matching|
| `DreamPoints`   | Cumulative fantasy points total    |
| `Specialism`    | Player role (BATTER/BOWLER/etc.)   |

Other columns are ignored by the system but preserved.
