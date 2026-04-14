#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  build_mac.sh  –  Build MedScheduler.app for macOS
#
#  Usage
#  -----
#    chmod +x build_mac.sh
#    ./build_mac.sh
#
#  What it does
#  ------------
#  1. Checks that Python 3 (≥3.9) is available via the macOS framework build
#     (required for tkinter GUI support).
#  2. Creates an isolated virtual environment so nothing pollutes your system.
#  3. Installs openpyxl and PyInstaller inside it.
#  4. Generates a colourful .icns icon on-the-fly (no external asset needed).
#  5. Runs PyInstaller with the provided .spec to produce MedScheduler.app.
#  6. Opens the dist/ folder in Finder when done.
#
#  Prerequisites (one-time)
#  ------------------------
#    Install Python from https://www.python.org/downloads/macos/
#    (The Apple-bundled Python does NOT include tkinter.)
#
#    Or with Homebrew:
#      brew install python-tk
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
die()     { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

echo -e "\n${BOLD}MedScheduler – macOS Build Script${NC}\n"

# ── 1. Locate a framework Python with tkinter ─────────────────────────────────
info "Searching for a framework Python (needed for tkinter GUI)..."

PYTHON=""
# Candidates in preference order
CANDIDATES=(
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.9/bin/python3"
    "$(brew --prefix 2>/dev/null)/bin/python3"
    "/usr/local/bin/python3"
    "python3"
)

for cand in "${CANDIDATES[@]}"; do
    if command -v "$cand" &>/dev/null 2>&1; then
        if "$cand" -c "import tkinter" &>/dev/null 2>&1; then
            PYTHON="$cand"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    die "No Python with tkinter found.\n\nInstall from https://www.python.org/downloads/macos/\nor run:  brew install python-tk"
fi

PY_VER=$("$PYTHON" --version 2>&1)
success "Using $PY_VER at $PYTHON"

# ── 2. Virtual environment ────────────────────────────────────────────────────
VENV_DIR="$SCRIPT_DIR/.venv_build"
if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment at $VENV_DIR ..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

PY="$VENV_DIR/bin/python3"
PIP="$VENV_DIR/bin/pip"

info "Upgrading pip..."
"$PIP" install --quiet --upgrade pip

# ── 3. Install dependencies ───────────────────────────────────────────────────
info "Installing openpyxl and pyinstaller..."
"$PIP" install --quiet openpyxl pyinstaller
success "Dependencies installed."

# ── 4. Generate icon ──────────────────────────────────────────────────────────
ICNS="$SCRIPT_DIR/MedScheduler.icns"
if [ ! -f "$ICNS" ]; then
    info "Generating app icon..."
    "$PY" - <<'PYEOF'
import os, struct, zlib, sys

# Build a minimal PNG in memory (no Pillow needed)
def make_png(size, bg, fg):
    def u32(n): return struct.pack('>I', n)
    def chunk(name, data):
        c = zlib.crc32(name + data) & 0xFFFFFFFF
        return u32(len(data)) + name + data + u32(c)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
    rows = []
    for y in range(size):
        row = [0]  # filter byte
        for x in range(size):
            dx, dy = x - size//2, y - size//2
            # Outer circle
            if dx*dx + dy*dy < (size*0.45)**2:
                # Inner cross (medical)
                if abs(dx) < size*0.1 or abs(dy) < size*0.1:
                    row += list(fg)
                else:
                    row += list(bg)
            else:
                row += [255, 255, 255]
        rows.append(bytes(row))
    raw = b''.join(rows)
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend

# Medical blue + white cross
bg  = (30, 100, 200)   # rich blue
fg  = (255, 255, 255)  # white cross

import tempfile, subprocess, shutil

tmpdir = tempfile.mkdtemp()
iconset = os.path.join(tmpdir, 'MedScheduler.iconset')
os.makedirs(iconset)

sizes = [16, 32, 64, 128, 256, 512, 1024]
for s in sizes:
    png = make_png(s, bg, fg)
    fname = f'icon_{s}x{s}.png'
    with open(os.path.join(iconset, fname), 'wb') as f:
        f.write(png)
    if s <= 512:
        fname2 = f'icon_{s//2 if s > 16 else 16}x{s//2 if s > 16 else 16}@2x.png'
        with open(os.path.join(iconset, fname2), 'wb') as f:
            f.write(make_png(s, bg, fg))

out_icns = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MedScheduler.icns')
result = subprocess.run(['iconutil', '-c', 'icns', iconset, '-o', out_icns], capture_output=True)
shutil.rmtree(tmpdir)
if result.returncode == 0:
    print(f"Icon written to {out_icns}")
else:
    print(f"iconutil failed (non-fatal): {result.stderr.decode()}")
PYEOF
    success "Icon generated."
else
    info "Icon already exists – skipping generation."
fi

# ── 5. Clean previous build ───────────────────────────────────────────────────
info "Cleaning previous build artefacts..."
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist"

# ── 6. Run PyInstaller ────────────────────────────────────────────────────────
info "Running PyInstaller..."
"$VENV_DIR/bin/pyinstaller" \
    --noconfirm \
    --log-level WARN \
    "$SCRIPT_DIR/MedScheduler.spec"

APP_PATH="$SCRIPT_DIR/dist/MedScheduler.app"

if [ -d "$APP_PATH" ]; then
    success "Build complete!"
    echo -e "\n${BOLD}App location:${NC}"
    echo "  $APP_PATH"
    echo -e "\n${BOLD}To run:${NC}"
    echo "  open \"$APP_PATH\""
    echo "  # or double-click MedScheduler.app in Finder"
    echo ""
    # Open Finder at dist/
    open "$SCRIPT_DIR/dist/" 2>/dev/null || true
else
    die "Build failed – MedScheduler.app not found in dist/"
fi
