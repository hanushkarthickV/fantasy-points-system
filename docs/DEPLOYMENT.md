# Deployment Guide — Fantasy Points System V2

## Option A: Deploy on existing Render project (Recommended)

Since V2 is backwards-compatible (V1 routes still work), you can **update the existing
Render project** by switching the branch:

1. Go to your Render dashboard → your web service
2. Under **Settings → Build & Deploy**:
   - Change **Branch** from `main` / `version-1` → `version-2`
3. Under **Environment → Environment Variables**, add:
   ```
   DATABASE_URL = postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres
   JWT_SECRET   = your-secret-key-here
   ```
4. Click **Manual Deploy → Deploy latest commit**
5. The build command should be:
   ```bash
   cd frontend && npm install && npm run build && cd .. && pip install -r backend/requirements.txt
   ```
6. The start command should be:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```

### Secret files (Google Sheets)
- Under **Settings → Secret Files**, add `google_service_account.json`
  with the path `/etc/secrets/google_service_account.json`
- This is the Google service account key for the `fantasy-points-bot` account

### Chrome for Selenium
Render's free-tier instances run on Linux. You need Chrome + ChromeDriver:
- Add a `render.yaml` or use the **Environment → Build Command** to install Chrome:
  ```bash
  apt-get update && apt-get install -y chromium chromium-driver
  ```
- Or use the `render-build.sh` script (see repo root)

---

## Option B: Deploy as a separate Render project

If you want to keep V1 and V2 running independently:

1. Create a **new Web Service** on Render
2. Connect the same GitHub repo, but select branch `version-2`
3. Follow the same env var and build command setup as above
4. You'll get a new URL (e.g., `fantasy-points-v2.onrender.com`)

### Pros of separate project
- V1 stays untouched, zero risk
- Can test V2 independently

### Cons
- Two free-tier instances = double the cold starts
- Need to manage two deployments

---

## Recommendation

**Use Option A** (update existing project). V2 includes all V1 routes, so nothing breaks.
The only addition is the database and new endpoints. Users who visit the frontend
will see the V2 interface automatically.

---

## Post-Deploy Checklist

1. ✅ Verify health: `curl https://your-app.onrender.com/health`
2. ✅ Sign up: hit `/api/v2/auth/signup` with your email
3. ✅ Login and open the frontend
4. ✅ Click "Sync Matches" to populate match list
5. ✅ Queue an extraction and verify it completes
6. ✅ Review points and update the sheet
7. ✅ Set up UptimeRobot to ping `/health` every 5 minutes (prevents cold starts)

---

## Troubleshooting

- **SSL errors on ESPN scraping**: The backend uses `verify=False` for `requests.get`.
  On Render (Linux), this usually works fine. If not, ensure the CA certificates are installed.
- **Chrome not found**: Selenium needs Chrome binary. Use the build script to install.
- **DB connection issues**: Supabase may require SSL. Add `?sslmode=require` to `DATABASE_URL`.
- **Port conflicts**: Render assigns `$PORT` env var automatically; Uvicorn reads it.
