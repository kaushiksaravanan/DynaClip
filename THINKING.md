# DynaClip - Repository Understanding

## What Is This?

DynaClip is a **lightweight, Windows-only clipboard history manager** built as a single-file Python application. It presents itself as a thin horizontal bar at the top of the screen that auto-shows when the user moves their mouse to the top edge (within 5px) and auto-hides when the mouse leaves. It remembers everything copied to the clipboard during the session, allowing quick recall, search, and reuse.

**Privacy is a core design principle:** nothing is persisted to disk -- the entire history lives only in RAM and vanishes when the app closes.

- **Author:** kaushiksaravanan
- **License:** CC0 1.0 Universal (public domain) -- note: README says MIT, but the actual LICENSE file is CC0.

---

## Tech Stack

| Layer            | Technology                                         |
| ---------------- | -------------------------------------------------- |
| Language         | Python 3                                           |
| GUI Framework    | tkinter (standard library)                         |
| Windows API      | ctypes (direct Win32 calls to `user32.dll`)        |
| Packaging        | PyInstaller (`--onefile --noconsole`)               |
| External Deps    | **None** -- 100% Python standard library           |

---

## Directory Structure

```
DynaClip/
├── .git/                    # Git metadata
├── .gitattributes           # LF normalization
├── LICENSE                  # CC0 1.0 Universal
├── README.md                # User-facing documentation
├── dynaclip.py              # THE ENTIRE APP (702 lines, single file)
├── DynaClip.bat             # Windows launcher (pythonw dynaclip.py)
├── DynaClip.spec            # PyInstaller build spec
├── build/                   # PyInstaller intermediate artifacts
│   └── DynaClip/
│       ├── Analysis-00.toc
│       ├── base_library.zip
│       ├── DynaClip.pkg
│       ├── EXE-00.toc, PKG-00.toc, PYZ-00.toc
│       ├── localpycs/       # Compiled .pyc bytecode
│       ├── warn-DynaClip.txt
│       └── xref-DynaClip.html
└── dist/                    # Distribution output
    └── DynaClip.exe         # Standalone executable
```

---

## Key Files

| File               | Role                                                                 |
| ------------------ | -------------------------------------------------------------------- |
| `dynaclip.py`      | Complete application source -- all logic, UI, clipboard, Win32 calls |
| `DynaClip.bat`     | Two-line batch launcher: `pythonw dynaclip.py`                       |
| `DynaClip.spec`    | PyInstaller spec: onefile, noconsole, UPX compression                |
| `dist/DynaClip.exe`| Pre-built standalone Windows executable                              |
| `README.md`        | Documentation: features, usage, settings, FAQ                        |
| `LICENSE`          | CC0 1.0 Universal (public domain)                                    |

---

## Architecture & Classes

The entire application lives in `dynaclip.py` with **three classes** and a `main()` entry point:

### 1. `ClipboardItem` -- Data Model
- Value object with `__slots__` for memory optimization.
- Fields: `id` (int), `text` (str), `timestamp` (datetime).
- Computed properties: `display_text` (truncated to 40 chars, single-line), `formatted_timestamp` (HH:MM).

### 2. `ModernTheme` -- Theme System
- Centralized color system with auto Windows dark/light mode detection.
- Reads `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\AppsUseLightTheme` from the Windows registry.
- Defines 12 semantic color tokens (bg_primary, bg_secondary, bg_card, bg_card_hover, fg_primary, fg_secondary, fg_muted, accent, accent_hover, border, success, danger) for both dark and light modes.
- Falls back to dark mode on detection error.

### 3. `DynaClip` -- Main Application Controller
- Monolithic controller: UI builder, event loop manager, business logic -- all in one class.
- **Constants:**
  - `BAR_HEIGHT = 64` pixels
  - `TRIGGER_ZONE = 5` pixels from top edge
  - `HIDE_DELAY = 600` ms before auto-hiding
  - `MAX_ITEMS = 50` (memory cap)

---

## How It Works

### Startup Flow
1. `main()` instantiates `DynaClip`, which creates a `ModernTheme`.
2. A tkinter root window is created: borderless (`overrideredirect`), always-on-top, near-opaque (0.98 alpha).
3. Window is set as a **tool window** (`WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE`) via Win32 API -- no taskbar entry, no focus steal.
4. UI is built: logo, "Add" button, gear/settings button, search box, scrollable horizontal item container, status label.
5. Window starts **off-screen** (above top edge by `BAR_HEIGHT - 1`).
6. Two polling loops start via `tkinter.after()`.

### Mouse Monitoring (50ms polling)
- Queries cursor position via `user32.GetCursorPos`.
- Determines which physical monitor the cursor is on via `user32.MonitorFromPoint`.
- If cursor Y is within `TRIGGER_ZONE` (5px) of monitor top edge → bar slides into view on that monitor.
- When mouse leaves, 600ms timer starts; if mouse hasn't returned, bar hides.

### Clipboard Monitoring (500ms polling)
- Reads system clipboard via `tkinter.clipboard_get()`.
- Detects changes from last known value.
- Items are **not** auto-added; user must click "Add" button. This is deliberate.

### Multi-Monitor Support
- Uses `MonitorFromPoint` and `GetMonitorInfoW` Win32 APIs for monitor detection.
- Bar resizes to the **work area** width (excluding taskbar) of the active monitor.
- Works across any number of monitors.

### Item Management
- Stored in a Python list (`self.items`), newest first.
- Capped at 50 items.
- Configurable duplicate handling (toggle via settings). When duplicates disallowed, re-copying moves existing entry to top.
- Click an item → copies it back to clipboard.
- Each item has a delete (x) button.
- Search filters in real-time (case-insensitive substring match).

### UI Details
- Horizontal scrollable card layout (tkinter Canvas with embedded frames).
- Mouse-wheel scrolls horizontally.
- Hover effects on cards (border color, background lightening).
- Tooltips after 400ms hover (up to 500 chars of full text).
- Status messages auto-clear after 2500ms.
- Escape key hides the bar.

### Settings Menu
- Context menu: Clear All (with confirmation), Toggle Allow Duplicates, item count, Exit.

---

## Build & Run

| Task         | Command                                                                    |
| ------------ | -------------------------------------------------------------------------- |
| Run (dev)    | `pythonw dynaclip.py` or double-click `DynaClip.bat`                      |
| Build exe    | `pip install pyinstaller && python -m PyInstaller --onefile --noconsole --name DynaClip dynaclip.py` |
| Output       | `dist/DynaClip.exe`                                                       |
| Tests        | None -- no test files, frameworks, or scripts exist                        |
| CI/CD        | None -- no GitHub Actions or pipeline config                               |
| Linting      | None configured                                                            |

---

## Notable Design Patterns

1. **Single-file architecture:** 702 lines, zero external dependencies. Maximally portable.

2. **Memory-only, privacy-first:** No file I/O, no network calls, no persistence. History exists only in RAM.

3. **`__slots__` optimization:** `ClipboardItem` uses `__slots__` for reduced per-instance memory overhead.

4. **Win32 API via ctypes:** Defines `ctypes.Structure` subclasses inline (POINT, RECT, MONITORINFO) and calls `user32.dll` directly. Avoids `pywin32` dependency.

5. **Labels as buttons:** Uses `tkinter.Label` with `cursor="hand2"` and manual bindings instead of `tkinter.Button` for full visual control.

6. **Polling over events:** Both mouse (50ms) and clipboard (500ms) use `tkinter.after()` polling rather than hooks or threads. Keeps app single-threaded and avoids tkinter thread-safety issues.

7. **Responsive multi-monitor:** Dynamically repositions to whichever monitor triggers it, querying real-time geometry from Win32.

8. **OS theme auto-detection:** Reads Windows registry for light/dark preference; falls back to dark mode.

---

## Open Observations

- **License discrepancy:** README says "MIT" but `LICENSE` file is CC0 1.0 Universal. Both permissive, but technically different.
- **Git history is minimal:** Only 3 commits, indicating a new/one-shot project.
- **No tests, no CI, no linting** -- straightforward utility with no quality gates.
- **Clipboard polling vs. hooks:** The 500ms polling approach is simpler but less responsive than Win32 clipboard chain listeners (`SetClipboardViewer` / `AddClipboardFormatListener`).
- **Items not auto-added:** Users must manually click "Add" -- this is a UX choice that could surprise users expecting automatic capture.
