# MedScheduler Web App — Deployment Guide

## What's in this folder

| File | Purpose |
|------|---------|
| `app.py` | Flask backend (REST API + Firebase token verification) |
| `scheduler.py` | Pure-Python scheduling engine (shared with desktop app) |
| `templates/index.html` | Single-page frontend (Firebase JS SDK, vanilla JS) |
| `requirements.txt` | Python dependencies (Flask, gunicorn, openpyxl) |
| `Procfile` | Process declaration for Render / Railway / Heroku |
| `runtime.txt` | Python version pin |

---

## Option A — Render (recommended, free tier available)

1. Push the entire `web/` folder contents to a **GitHub repository** (the repo root should contain `app.py`, `requirements.txt`, `Procfile`, `runtime.txt`, and the `templates/` folder).

2. Go to https://render.com → **New → Web Service**.

3. Connect your GitHub repo. Render auto-detects `Procfile`.

4. Set:
   - **Environment**: Python
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: *(auto-read from Procfile)*

5. Add these **environment variables** in Render dashboard:
   ```
   FIREBASE_PROJECT_ID   = 
   FIREBASE_API_KEY      = 
   ```

6. Click **Deploy**. Render gives you a public URL like `https://medscheduler.onrender.com`.

---

## Option B — Railway

1. Push `web/` contents to GitHub (same structure as above).
2. Go to https://railway.app → **New Project → Deploy from GitHub Repo**.
3. Railway detects `Procfile` automatically.
4. Add environment variables (same as above) under **Variables** tab.
5. Deploy. Railway gives you a public URL.

---

## Option C — Run locally for testing

```bash
cd web/
pip install -r requirements.txt
export FIREBASE_PROJECT_ID=
export FIREBASE_API_KEY=
flask run --port 5000
# open http://localhost:5000
```

---

## Firebase Console setup (required once)

### Authentication
1. Firebase Console → **Authentication → Sign-in method**
2. Enable **Email/Password**

### Firestore
1. Firebase Console → **Firestore Database → Rules**
2. Paste and publish:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /shared/schedule {
      allow read, write: if request.auth != null;
    }
  }
}
```
This lets any signed-in team member read/write the shared schedule.

> **NOTE (2026-06):** the snippet above is the original single-schedule rules and is
> kept for historical reference only. The CURRENT rules text lives in
> `web/firestore.rules` (workspaces + invites + notifications + audit) — paste
> THAT file when publishing.

### Audit-log retention — Firestore TTL (cycle 4 / D14 — ACTIVATION DEFERRED 2026-06-11)

> Status: NOT enabled (user decision — history kept indefinitely for now).
> The app already writes `expire_at` on every audit entry, so enabling the
> policy below at any future date turns on 90-day retention with no code
> change. ⚠ Activating later purges retroactively: every entry already older
> than 90 days is deleted within ~24 h of activation.

Audit entries (`workspaces/{wsId}/audit/{entryId}`) carry an `expire_at`
timestamp set 90 days after creation (`AUDIT_RETENTION_DAYS` in `app.py`).
Firestore deletes expired entries server-side via a TTL policy — security
rules still deny all user deletes, so history stays immutable for users.

1. Google Cloud Console → **Firestore → Time-to-live (TTL)** (or Firebase Console → Firestore → TTL tab)
2. **Create policy**: collection group `audit`, timestamp field `expire_at`
3. Wait until the policy state shows **Active** (can take a few minutes)

Or via gcloud:
```
gcloud firestore fields ttls update expire_at \
  --collection-group=audit --enable-ttl --project=medscheduler-e0853
```

Notes:
- TTL deletion typically runs within ~24 h after `expire_at` — fine for retention.
- Entries written before cycle 4 have no `expire_at` and never auto-expire;
  delete them manually in the Console once if you want a clean cut.
- Disabling the policy stops future deletions; already-deleted entries are gone.

### Authorised domains (for web sign-in)
1. Firebase Console → **Authentication → Settings → Authorised domains**
2. Add your Render/Railway domain, e.g. `medscheduler.onrender.com`

---

## How the multi-user model works

- **One shared schedule** stored at Firestore path `shared/schedule`.
- Any team member who signs in with a Firebase account can load, edit, and save the schedule.
- All changes are saved to the cloud — no local files needed.
- The Flask backend verifies the Firebase ID token on every API call, so only authenticated users can modify data.

---

## Inviting team members

Go to **Firebase Console → Authentication → Users → Add user** and create an email/password account for each team member. They can then sign in at your deployed URL.
