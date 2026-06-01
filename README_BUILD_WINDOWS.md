# MedScheduler - Windows build notes

## What is already in the source
- Main desktop app: `medscheduler_refactored.py`
- Desktop dependency: `openpyxl`
- Firebase sync uses built-in `urllib`, so no extra networking package is required.
- The current provided spec file is macOS-oriented because it ends with a `BUNDLE(...)` block for `MedScheduler.app`.

## Added for Windows
- `build_windows.bat` - one-click Windows build script
- `run_windows.bat` - one-click Windows run script without packaging
- `MedScheduler_windows.spec` - PyInstaller spec for Windows `.exe`

## Recommended Windows setup
1. Install official Python 3.11 or 3.12 for Windows from python.org.
2. During install, keep `tcl/tk and IDLE` enabled.
3. Open the project folder.
4. Double-click `run_windows.bat` to run the source app.
5. Double-click `build_windows.bat` to build the packaged app.

## Expected build output
Usually:
- `dist\MedScheduler\MedScheduler.exe`

Depending on PyInstaller options, it may also appear as:
- `dist\MedScheduler.exe`

## Notes
- The container used for this handoff is Linux, so a real Windows `.exe` cannot be generated here.
- The Python sources compile successfully, which confirms there is no syntax error in the main desktop app, Firebase service, or rota converter.
