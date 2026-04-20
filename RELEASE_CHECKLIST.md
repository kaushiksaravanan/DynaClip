# Release Checklist

- Run `python smoke_test.py`
- Run the app locally and verify the compact island appears on top-edge trigger
- Verify `Ctrl+Shift+Space` toggles the island
- Verify tray icon appears and menu actions work
- Verify auto-capture toggle persists across restart
- Verify startup toggle writes/removes startup launcher
- Verify text clipboard add/copy
- Verify file clipboard add/copy
- Verify image clipboard add/copy
- Verify detail pop-out windows open and close cleanly
- Verify multi-monitor positioning
- Build with `python -m PyInstaller DynaClip.spec`
- Smoke-test the built `dist/DynaClip.exe`
- Verify logs are created under `%LOCALAPPDATA%\DynaClip\logs`
- Sign the executable before distribution
