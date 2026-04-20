# Pre-Release Audit

## Status

DynaClip is in strong pre-release shape but is not yet fully release-verified.

## What Looks Good

- Single-instance protection exists
- Dynamic Island behavior is implemented
- Tray icon and global hotkey exist
- Settings persistence exists
- Startup registration exists
- Text, file-list, and bitmap-image clipboard support exists
- Multi-window clip pop-outs exist
- Packaging metadata exists (`DynaClip.spec`, `version_info.txt`, `dynaclip.ico`)
- Release workflow docs/scripts exist

## Remaining Release Blockers

### 1. Built executable not yet validated
- `PyInstaller` was not available in the current environment
- `dist\DynaClip.exe` must be rebuilt and tested after the latest source changes

### 2. Runtime Windows QA still required
- Tray callbacks need live Windows verification
- File/image clipboard round-trip needs live Windows verification
- Startup behavior must be tested with sign-out / reboot
- Multi-monitor behavior must be tested on real hardware setups

### 3. Installer not yet tested
- `DynaClip.iss` has been added but not compiled/tested
- Install/uninstall/startup task behavior needs validation

### 4. Security / trust still pending
- No code signing yet
- Unsigned PyInstaller apps may trigger SmartScreen / antivirus warnings

## Lower-Priority Risks

- Many defensive `except Exception` blocks exist around Win32 paths; acceptable for resilience, but live logs should be reviewed during QA
- No automated integration/UI test suite yet
- Image support is clipboard-format based, but no visual preview rendering is included yet

## Recommended Release Steps

1. Install `pyinstaller`
2. Run `powershell -ExecutionPolicy Bypass -File .\build_release.ps1`
3. Test `dist\DynaClip.exe` with `QA_MATRIX.md`
4. Compile `DynaClip.iss` with Inno Setup
5. Test installer install / launch / uninstall
6. Sign the executable and installer

## Suggested Release Decision

- `NO-GO` until built exe + installer + manual QA are completed
- `GO` after those validations pass
