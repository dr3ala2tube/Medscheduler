# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for MedScheduler – macOS .app bundle
# Run:  pyinstaller MedScheduler.spec

import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['medscheduler_refactored.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=(
        collect_submodules('openpyxl') +
        collect_submodules('tkinter') +
        ['tkinter', 'tkinter.ttk', 'tkinter.messagebox',
         'tkinter.filedialog', 'tkinter.simpledialog',
         '_tkinter',
         # firebase_service.py uses these stdlib modules
         'urllib', 'urllib.request', 'urllib.parse',
         'urllib.error', 'urllib.response', 'urllib.robotparser',
         'http', 'http.client', 'http.cookiejar',
         'email', 'email.mime', 'email.mime.multipart',
         'json', 'threading', 'ssl']
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'PIL', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MedScheduler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No terminal window on macOS
    disable_windowed_traceback=False,
    target_arch=None,       # None = native arch (works for both Intel & Apple Silicon)
    codesign_identity=None,
    entitlements_file=None,
    icon='MedScheduler.icns' if sys.platform == 'darwin' else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MedScheduler',
)

app = BUNDLE(
    coll,
    name='MedScheduler.app',
    icon='MedScheduler.icns',
    bundle_identifier='com.medscheduler.app',
    info_plist={
        'CFBundleName': 'MedScheduler',
        'CFBundleDisplayName': 'MedScheduler',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,   # supports Dark Mode
        'LSMinimumSystemVersion': '10.14',
    },
)
