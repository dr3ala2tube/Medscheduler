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
   FIREBASE_PROJECT_ID   = medscheduler-e0853
   FIREBASE_API_KEY      = AIzaSyC_d-HgnEnLAWW1f3dSKjuuAz4eplcVWz8
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
export FIREBASE_PROJECT_ID=medscheduler-e0853
export FIREBASE_API_KEY=AIzaSyC_d-HgnEnLAWW1f3dSKjuuAz4eplcVWz8
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
