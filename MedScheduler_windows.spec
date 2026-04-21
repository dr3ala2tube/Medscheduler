# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for MedScheduler on Windows
# Build with: py -3.11 -m PyInstaller --noconfirm --clean MedScheduler_windows.spec

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hidden = (
    collect_submodules('openpyxl') +
    collect_submodules('tkinter') +
    [
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox',
        'tkinter.filedialog', 'tkinter.simpledialog',
        '_tkinter',
        'urllib', 'urllib.request', 'urllib.parse',
        'urllib.error', 'urllib.response', 'urllib.robotparser',
        'http', 'http.client', 'http.cookiejar',
        'email', 'email.mime', 'email.mime.multipart',
        'json', 'threading', 'ssl'
    ]
)

a = Analysis(
    ['medscheduler_refactored.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
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
    console=False,
    disable_windowed_traceback=False,
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
