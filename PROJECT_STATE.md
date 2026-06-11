# MedScheduler — Project State (Last updated: June 11, 2026)

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

**Firestore rules:** see `web/firestore.rules` (deployed 2026-06-10 via Firebase Console).
Data model (since June 2026, "private workspaces" feature):

| Firestore path | Purpose | Access |
|---|---|---|
| `workspaces/{uid}` | Workspace meta/ACL: `owner_uid`, `owner_email`, `members` (lowercase emails) | Owner full; members read; only owner edits membership |
| `workspaces/{uid}/data/schedule` | Schedule payload (same shape as old shared doc) | Owner + invited members, full read/write |
| `workspaces/{uid}/audit/{entryId}` | Immutable audit trail — one entry per web save: actor email, ISO timestamp, summary, change lines | Owner + members create (own actor_email only) and read; NOBODY can update/delete |
| `shared/schedule` | LEGACY old team-wide doc, kept as inert backup | Unreachable (no rules block grants access since cycle 2) |

**Sharing model:** every account gets a private workspace (auto-created on first
login). The owner invites colleagues by email via the 👥 Share button; invited
users see the workspace in a header dropdown and can edit it. Removing the email
revokes access instantly (enforced by Firestore rules, verified live 2026-06-10
incl. direct-REST 403 check). Old rules backup: Firebase Console → Rules history.

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
- `FirebaseService` class: `sign_in()`, `sign_up()`, `sign_out()`, `get_workspaces()`, `save_app_data(workspace_id)`, `load_app_data(workspace_id)`, `upload_file()`, `list_files()`, `download_file()`
- **New workspace model (June 2026)** — `get_workspaces()` returns own + shared workspaces; `save_app_data()` and `load_app_data()` accept optional `workspace_id` parameter (defaults to user's own uid)
- Firestore document path: `workspaces/{workspace_id}/data/schedule` (new); `shared/schedule` (legacy, read-only)
- `_py_to_fs(value)` / `_fs_to_py(value)` — Firestore typed-value serialization
- Module-level singleton: `firebase = FirebaseService()`

---

## Web App — What Was Built

### Architecture
- **Multi-user**: private per-user Firestore workspaces with email-invite sharing (see Firebase section above); access enforced by Firestore security rules — Flask only relays the caller's own ID token
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
| `/api/workspaces` | GET | Yes | Own workspace (auto-created) + workspaces shared with me |
| `/api/workspaces/members` | POST | Yes | Owner adds/removes an invited member email |
| `/api/data?ws=<id>` | GET | Yes | Loads a workspace schedule (default: own) |
| `/api/data?ws=<id>` | POST | Yes | Saves a workspace schedule (default: own) |
| `/api/data/import-legacy` | POST | Yes | One-time copy of old shared doc into own empty workspace |
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

## Access Control (who sees what)

Since June 2026, signing in no longer grants access to any shared data:
- **Every account gets only its own private, empty workspace**
- **New accounts (created on/after 2026-06-10) must verify their email** before the app or API accepts them; older accounts are grandfathered
- Schedule access is granted per-workspace by the owner via 👥 Share — since 2026-06-10 this sends a **pending invitation** the recipient must Accept (or can Decline); members can later Leave via the 🚪 button
- Owners get in-app notifications (🔔 bell, 60s poll) when an invitation is accepted/declined or a member leaves
- Enforcement is in Firestore security rules (`web/firestore.rules`), not in the app —
  verified by direct REST probe returning 403 for revoked/uninvited users
- Self-signup is still open, but a new account sees nothing until invited
- Optional hardening (unchanged): email allowlist check after sign-in
- (Cycle 3, 2026-06-11) **Audit trail**: every web save writes who/when/what (server-side diff) to `workspaces/{ws}/audit`; 📜 History button (next to the 🔔 bell) shows it to owner and members; entries are immutable for everyone
- (Cycle 3) **Conflict detection**: duplicate single-slot assignments (duty DM/DF or clinic on the same day) warn at edit time, highlight red, and show a ⚠ chip — never block saving (override allowed)
- (Cycle 3) **Password reset**: "Forgot password?" on the sign-in card (enumeration-safe — same message whether or not the account exists)
- (Cycle 4, 2026-06-11) **Audit retention mechanism**: every new audit entry carries `expire_at` (created + 90 d, `AUDIT_RETENTION_DAYS` in app.py); rules v4 accept the optional field. **TTL policy NOT enabled (user decision — history kept indefinitely)**; activation steps + retroactive-purge warning in web/DEPLOY.md
- (Cycle 4) **Conflict scope v2**: in addition to duplicate slots, conflicts now flag working codes during an approved leave and working codes within `post_call_days` after a duty (both warn-then-override at cell edit / Manual Assign; typed entries in the ⚠ conflicts modal; month-boundary windows truncate — documented limitation)
- (Cycle 4) **Dark & light themes**: 🌓 toggle (header + sign-in screen) cycles Auto/Light/Dark, persisted per device in localStorage (`ms-theme`), Auto follows OS; schedule grid intentionally stays light in both themes (per-code colors are data); fixes during live matrix: `.btn-cancel` missing text color (dark mode), Summary-tab column misalignment (pre-existing nested-`<tr>` bug)
- (Cycle 4) **Summary tab rework (M20)**: Team column → Morning Days (all 8-hr work days incl. clinics); Off → Random Off; Weekend Off → Weekends Inc in Offs; new last column Total Off Days = Post-Call + O/R + Leave (`morning` field added to compute_summary; desktop summary unaffected)

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

- [x] **Deploy to Render** — live at `https://medscheduler-5io6.onrender.com` (June 2026)
- [x] **Test web app end-to-end** — full two-account verification matrix passed 2026-06-10
- [x] **Private workspaces + invite sharing** — shipped 2026-06-10 (see PROJECT_MAP.md)
- [x] **Desktop app workspace migration** — completed 2026-06-10: `firebase_service.py` now supports `get_workspaces()`, parameterized `save_app_data(workspace_id)` / `load_app_data(workspace_id)` targeting `workspaces/{id}/data/schedule`; `medscheduler_refactored.py` UI updated with workspace selector dropdown and selection dialog after login
- [x] **Cycle 2 shipped 2026-06-10** — first-login import popup removed; email verification for new signups (cutoff 2026-06-10 UTC, constant in app.py + index.html); invitation accept/decline/leave + notifications panel; UI fixes (#undefined cell color, dynamic max-hours highlight, header clipping, mobile touch targets). Rules v2 published (Console rules history = rollback)
- [x] **Remove legacy rules block** — done in cycle 2; `shared/schedule` doc remains in Firestore as an inert backup
- [x] **Cycle 3 shipped 2026-06-11** — conflict detection (warn + override, derived client-side, nothing persisted); immutable audit trail + History UI (`/api/audit`, rules v3 published); 📜 moved to header row 1 + action-row compaction (desktop overflow fix); password reset on sign-in card. Branch `feature/conflicts-audit`, merged via PR; details in PROJECT_MAP.md cycle 3
- [x] **Cycle 4 shipped 2026-06-11** — 90-day audit-retention mechanism (`expire_at`, rules v4 published; TTL activation DEFERRED by user — flip on anytime via DEPLOY.md, beware retroactive purge); conflict scope v2 (leave-day + missing post-call rest, warn + override); dark/light themes (auto/light/dark, per-device); Summary tab rework (Morning Days, Random Off, Weekends Inc in Offs, Total Off Days). Live-matrix fixes: `.btn-cancel` dark-mode text, Summary nested-`<tr>` alignment. Branch `feature/retention-conflicts-themes`, merged via PR; details in PROJECT_MAP.md cycle 4
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
export FIREBASE_