# MedScheduler – Complete Transfer Guide

## GitHub Repository
- **Remote URL**: https://github.com/dr3ala2tube/Medscheduler.git
- **Branch**: main
- After unpacking, run `git remote set-url origin https://github.com/dr3ala2tube/Medscheduler.git` if needed

## Firebase Project
- **Project ID**: medscheduler-e0853
- **API Key**: AIzaSyC_d-HgnEnLAWW1f3dSKjuuAz4eplcVWz8
- **Storage Bucket**: medscheduler-e0853.firebasestorage.app
- **Firestore**: shared document at `shared/schedule`
- ⚠️ These credentials are already embedded in `firebase_service.py` and `web/app.py` — no extra config needed.

## Project Structure
```
MedScheduler/
├── medscheduler_refactored.py   # Main desktop Tkinter app
├── firebase_service.py          # Firebase REST API (auth, Firestore, Storage)
├── rota_converter.py            # Excel rota conversion logic
├── requirements.txt             # Python dependencies (desktop)
├── run_mac.sh                   # Run desktop app on macOS
├── build_mac.sh                 # Build macOS .app bundle
├── run_converter_mac.sh         # Run rota converter
├── MedScheduler.spec            # PyInstaller spec file
├── April2026_Rota.xlsx          # Current rota spreadsheet
├── REFERENCE.md                 # Architecture & technical reference
├── PROJECT_STATE.md             # Current project state & progress
├── Rota_Rules_Validation_Report.md
├── 🩺 Monthly Rota Rules.docx   # Scheduling rules document
└── web/
    ├── app.py                   # Flask backend (REST API)
    ├── scheduler.py             # Scheduling engine
    ├── requirements.txt         # Web dependencies
    ├── Procfile                 # Heroku/Railway deploy
    ├── runtime.txt              # Python version
    ├── DEPLOY.md                # Deployment instructions
    └── templates/
        └── index.html           # Single-page web UI
```

## Setup on New Machine

### Desktop App
```bash
cd MedScheduler
pip install -r requirements.txt
./run_mac.sh
```

### Web App (local)
```bash
cd MedScheduler/web
pip install -r requirements.txt
python app.py
```

### Python Requirements (desktop)
- tkinter (built-in)
- openpyxl
- requests (or urllib — firebase_service uses only built-ins)

### Python Requirements (web)
- flask
- openpyxl
- gunicorn (for deployment)

## Git Setup on New Machine
```bash
# If cloning fresh from GitHub:
git clone https://github.com/dr3ala2tube/Medscheduler.git

# OR unzip this archive and push:
cd MedScheduler
git remote set-url origin https://github.com/dr3ala2tube/Medscheduler.git
git push --set-upstream origin main
```

## Cowork / Claude Desktop Setup
- Place the MedScheduler folder as your selected workspace folder
- The REFERENCE.md and PROJECT_STATE.md files provide full context for Claude
