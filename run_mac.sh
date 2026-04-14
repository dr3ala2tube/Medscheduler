#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  run_mac.sh  –  Quick-run MedScheduler directly (no build step)
#
#  Usage
#  -----
#    chmod +x run_mac.sh
#    ./run_mac.sh
#
#  Works with Python installed via Homebrew, python.org, or pyenv.
#  Dependencies are installed inside a local .venv_run/ folder so that
#  nothing touches your system or Homebrew environment.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
die()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 1. Find a Python 3 that includes tkinter ─────────────────────────────────
PYTHON=""

# Prefer the official python.org framework build (always has tkinter).
# Fall back to Homebrew python-tk, then any python3 in PATH.
CANDIDATES=(
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.9/bin/python3"
)

# Also check Homebrew prefix dynamically
BREW_PREFIX="$(brew --prefix 2>/dev/null || true)"
if [ -n "$BREW_PREFIX" ]; then
    # python-tk installs a wrapper that has tkinter
    for minor in 13 12 11 10 9; do
        CANDIDATES+=("$BREW_PREFIX/opt/python@3.$minor/bin/python3.$minor")
    done
    CANDIDATES+=("$BREW_PREFIX/bin/python3")
fi

CANDIDATES+=("/usr/local/bin/python3" "python3")

for cand in "${CANDIDATES[@]}"; do
    # Expand the path (handles plain command names)
    resolved="$(command -v "$cand" 2>/dev/null || true)"
    [ -z "$resolved" ] && continue
    if "$resolved" -c "import tkinter" &>/dev/null 2>&1; then
        PYTHON="$resolved"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    die "No Python with tkinter found on this machine.

── How to fix ──────────────────────────────────────────────────────
Option A (recommended – includes tkinter by default):
  Download Python from https://www.python.org/downloads/macos/
  and run the installer.

Option B (Homebrew):
  brew install python-tk

After installing, re-run this script."
fi

info "Using Python: $PYTHON  ($(\"$PYTHON\" --version 2>&1))"

# ── 2. Create / reuse a local virtual environment ────────────────────────────
VENV_DIR="$SCRIPT_DIR/.venv_run"

if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment at .venv_run/ ..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

VENV_PY="$VENV_DIR/bin/python3"
VENV_PIP="$VENV_DIR/bin/pip"

# ── 3. Install openpyxl if not already present ───────────────────────────────
if ! "$VENV_PY" -c "import openpyxl" &>/dev/null 2>&1; then
    info "Installing openpyxl into virtual environment..."
    "$VENV_PIP" install --quiet --upgrade pip
    "$VENV_PIP" install --quiet openpyxl
fi

# ── 4. Launch the app ─────────────────────────────────────────────────────────
echo -e "${GREEN}Launching MedScheduler...${NC}"
exec "$VENV_PY" "$SCRIPT_DIR/medscheduler_refactored.py"
