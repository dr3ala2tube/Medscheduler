# MedScheduler — Project State (Last updated: April 2026)

This file is the single source of truth for resuming work on MedScheduler.
Read this at the start of every new session instead of reconstructing from history.

---

## What Exists in This Folder

```
MedScheduler/
├── medscheduler_refactored.py   ← Desktop app (Python/Tkinter), all-in-one file
├── firebase_service.py          ← Firebase REST client (urllib only, zero extra deps)
├── requirements.txt             ← Desktop dependencies: openpyxl only (no requests)
├── MedScheduler.spec            ← PyInstaller spec for macOS .app build
├── build_mac.sh                 ← Run with: chmod +x build_mac.sh && ./build_mac.sh
├── run_mac.sh                   ← Direct Python launch shortcut
├── REFERENCE.md                 ← Deep scheduling-engine + desktop UI reference
├── PROJECT_STATE.md             ← THIS FILE — session continuity doc
└── web/                         ← Web app (Flask + Firebase JS SDK)
    ├── app.py                   ← Flask backend (REST API + Firebase token verify)
    ├── scheduler.py             ← Scheduling engine (pure Python, no UI, shared)
    ├── requirements.txt         ← Flask==3.0.3, gunicorn==22.0.0, openpyxl==3.1.2
    ├── Procfile                 ← gunicorn app:app (for Render/Railway/Heroku)
    ├── runtime.txt              ← python-3.11.9
    ├── DEPLOY.md                ← Step-by-step Render + Firebase deployment guide
    └── templates/
        └── index.html           ← Full single-page app (Firebase JS SDK CDN, vanilla JS)
```

---

## Firebase Configuration

**Project ID:** `medscheduler-e0853`
**API Key:** `AIzaSyC_d-HgnEnLAWW1f3dSKjuuAz4eplcVWz8`
**Auth Domain:** `medscheduler-e0853.firebaseapp.com`
**Storage Bucket:** `medscheduler-e0853.firebasestorage.app`
**Messaging Sender ID:** `34915686489`
**App ID:** `1:34915686489:web:2f62ad062e47558934f948`

**Sign-in method:** Email/Password (must be enabled in Firebase Console → Authentication → Sign-in method)

**Firestore rules** (paste in Firebase Console → Firestore → Rules):
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
**Shared data path:** `shared/schedule` (one document for the whole team)

**To add team members:** Firebase Console → Authentication → Users → Add user (email + password).
Only accounts you create here can log in — this is how access is restricted.

---

## Desktop App — What Was Built / Changed

**File:** `medscheduler_refactored.py`

### Firebase integration added
- Import block at top of file:
  ```python
  import threading
  try:
      from firebase_service import firebase, FirebaseAuthError, FirebaseNetworkError
      _FIREBASE_AVAILABLE = True
  except ImportError:
      _FIREBASE_AVAILABLE = False
      firebase = None
  ```
- Classes added before `MedSchedulerApp`: `LoginDialog`, `CloudFilesDialog`
- Methods added to `MedSchedulerApp`:
  - `_update_firebase_label()` — updates cloud status label in toolbar
  - `_firebase_login()` — opens LoginDialog, signs in via firebase_service
  - `_firebase_save()` — serializes app state → uploads to Firestore
  - `_firebase_load()` — downloads from Firestore → deserializes
  - `_firebase_files()` — opens CloudFilesDialog
  - `_apply_cloud_data(data)` — merges cloud data into local state
  - `_serialize_app()` — converts app state to JSON-serializable dict
  - `_deserialize_app(data)` — restores app state from dict

### Two-row toolbar (buttons were being cut off)
`build_ui()` creates two toolbar rows:
- `tb1`: Title + Month Nav + Firebase cloud panel (right-aligned with `side="right"`)
- `tb2`: All action buttons (Auto-Schedule, Assign Duty, Annual Leave, Block Specialty, Manual Assign, Export Rota, Export Full, Clear Month)

### Doctor import with initials
`parse_doctor_names()` returns `List[tuple]` of `(name, initials)`.

Supported import file formats (one physician per line):
```
DR. ALAA | AH
DR. SMITH	SM       ← tab-separated also works
DR. JONES            ← name only (initials left blank)
# comment lines and blank lines are skipped
```
`import_doctors()` applies initials to **existing** doctors on re-import (updates in place, doesn't duplicate).

---

## firebase_service.py — Key Facts

- **Zero third-party dependencies** — uses only Python's built-in `urllib`, `json`, `ssl`
- Written this way because macOS shows `externally-managed-environment` error with pip
- `FirebaseService` class: `sign_in()`, `sign_up()`, `sign_out()`, `save_app_data()`, `load_app_data()`, `upload_file()`, `list_files()`, `download_file()`
- `_py_to_fs(value)` / `_fs_to_py(value)` — Firestore typed-value serialization
- Module-level singleton: `firebase = FirebaseService()`
- Firestore document path: `shared/schedule`

---

## Web App — What Was Built

### Architecture
- **Multi-user**: one shared Firestore document for the whole team
- **Auth**: Firebase JS SDK on the client; Flask backend verifies ID token on every API call
- **No build step**: plain HTML + vanilla JS, Firebase CDN, no npm/webpack needed

### web/scheduler.py (454 lines)
Full scheduling engine extracted from desktop app. Pure Python, no UI, no dependencies beyond stdlib.
Exports everything `app.py` needs:
`auto_schedule`, `compute_summary`, `dim`, `ds`, `day_of_week`, `is_we`,
`Doctor`, `LeaveBlock`, `SpecialtyBlock`, `ManualAssignment`,
`SHIFTS`, `COLOR_MAP`, `MONTHS`, `DN`, `TEAMS`, `SUBS`, `MORNING_K`,
`DUTY_SET`, `OFF_SET`, `SPEC_OPTIONS`, `MANUAL_ASSIGN_CODES`, `BLOCKABLE_SPECIALTIES`

### web/app.py (416 lines)
Flask backend routes:

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/` | GET | No | Serves index.html |
| `/api/constants` | GET | No | Returns SHIFTS, COLOR_MAP, SPEC_OPTIONS, etc. |
| `/api/data` | GET | Yes | Loads shared schedule from Firestore |
| `/api/data` | POST | Yes | Saves shared schedule to Firestore |
| `/api/schedule` | POST | Yes | Runs auto_schedule(), returns asgn dict |
| `/api/summary` | POST | Yes | Returns per-physician statistics |
| `/api/export/rota` | POST | Yes | Returns .xlsx rota file |
| `/api/export/full` | POST | Yes | Returns .xlsx detailed export |

`@require_auth` decorator verifies Firebase ID token from `Authorization: Bearer <token>` header.

### web/templates/index.html (864 lines)
Single-page app. Key features:
- Firebase Auth screen (sign in / create account)
- **Two-row header**: Row 1 = logo + month nav + user badge; Row 2 = all action buttons
- Sidebar: Add Physician form + **Import from File** button + physician list
- Schedule grid: color-coded cells, sticky physician column, weekend highlighting, click to edit cell
- Summary tab: per-physician stats loaded async from `/api/summary`
- All modals: Cell Edit, Annual Leave, Block Specialty, Manual Assign
- Export: downloads .xlsx via Blob URL

### Import Physicians (web)
Button "⬆ Import from File" in sidebar accepts `.txt` or `.csv`.
Same format as desktop (see above). If physician name already exists → updates initials only. New names → added to list.

---

## Deployment Status

**GitHub repo:** `https://github.com/dr3ala2tube/Medscheduler`
(push the contents of the `web/` folder as the repo root)

**Target platform:** Render.com (free tier)

**Environment variables needed on Render:**
```
FIREBASE_PROJECT_ID = medscheduler-e0853
FIREBASE_API_KEY    = AIzaSyC_d-HgnEnLAWW1f3dSKjuuAz4eplcVWz8
```

**After deployment:** Add the Render URL to Firebase Console → Authentication → Settings → Authorized domains.

**Full step-by-step deployment guide:** `web/DEPLOY.md`

### GitHub push fix (for future reference)
GitHub no longer accepts passwords for git push. Must use a Personal Access Token:
1. Generate at: `https://github.com/settings/tokens` → Classic → tick "repo"
2. Use the token (`ghp_...`) as the password when git asks
3. Run once to save it: `git config --global credential.helper osxkeychain`

---

## Access Control (who can log in)

Firebase does not have a built-in email allowlist. The approach used here:
- **Only create Firebase accounts for people you want to have access**
- Firebase Console → Authentication → Users → Add user (email + password)
- Since you control account creation, only those accounts can ever sign in
- Optional enhancement: hardcode an email allowlist in `index.html` JS and check after sign-in

---

## Known Issues Fixed (do not re-introduce)

| Issue | Fix |
|-------|-----|
| `externally-managed-environment` pip error on macOS | Rewrote firebase_service.py to use urllib only — no pip install needed |
| `PASSWORD_LOGIN_DISABLED` Firebase error | Enable Email/Password in Firebase Console → Authentication → Sign-in method |
| Export buttons obscured in desktop toolbar | Split toolbar into two rows (tb1 + tb2) |
| Export buttons cut off in web app header | Split header into two rows (hdr-row1 + hdr-row2) |
| GitHub push rejected with password | Use Personal Access Token (ghp_...) instead of password |

---

## Pending / Next Steps

- [ ] **Deploy to Render** — push `web/` to GitHub, connect to Render, set env vars, add authorized domain
- [ ] **Test web app end-to-end** — sign in, add physicians, run auto-schedule, export
- [ ] **Add email allowlist** (optional) — check `user.email` after sign-in against a hardcoded list
- [ ] **Always-on Render** — upgrade to $7/month plan if the 30-second cold-start is annoying
- [ ] **Custom domain** (optional) — Render supports free custom domains

---

## Running the Desktop App

```bash
cd ~/Desktop/MedScheduler
python3 medscheduler_refactored.py
```

## Building the macOS .app

```bash
cd ~/Desktop/MedScheduler
chmod +x build_mac.sh
./build_mac.sh
# Output: dist/MedScheduler.app
```

## Running the Web App Locally (for testing)

```bash
cd ~/Desktop/MedScheduler/web
pip install -r requirements.txt
export FIREBASE_PROJECT_ID=medscheduler-e0853
export FIREBASE_API_KEY=AIzaSyC_d-HgnEnLAWW1f3dSKjuuAz4eplcVWz8
flask run --port 5000
# Open: http://localhost:5000
```

---

## For the Next Session

1. Read this file first (`PROJECT_STATE.md`)
2. Read `REFERENCE.md` if you need scheduling engine or desktop UI details
3. Read `web/DEPLOY.md` if deployment help is needed
4. The Firebase config above has all credentials — no need to ask the user again
