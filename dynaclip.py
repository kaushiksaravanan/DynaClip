#!/usr/bin/env python3
"""
DynaClip - Windows Dynamic Island for clipboard history.

A lightweight, in-memory clipboard history manager that appears as a
centered pill at the top of the current monitor. Clicking the pill expands
it into a clipboard shelf for quick recall and reuse.
"""

import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
from logging.handlers import RotatingFileHandler
from pathlib import Path
import logging
import os
import struct
import sys
import tkinter as tk
from tkinter import messagebox


GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
MONITOR_DEFAULTTONEAREST = 2
ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\DynaClipSingleton"
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
HOTKEY_ID = 1
HOTKEY_MODIFIERS = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
HOTKEY_LABEL = "Ctrl+Shift+Space"
WM_APP = 0x8000
TRAY_CALLBACK_MSG = WM_APP + 1
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B
GWL_WNDPROC = -4
IDI_APPLICATION = 32512
TRAY_UID = 1
APP_VERSION = "0.3.0"
SETTINGS_KEY = r"Software\DynaClip"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
CF_DIB = 8
CF_UNICODETEXT = 13
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040
GHND = GMEM_MOVEABLE | GMEM_ZEROINIT
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


def get_app_data_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"
    app_dir = base / "DynaClip"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def setup_logger() -> tuple[logging.Logger, Path | None]:
    logger = logging.getLogger("DynaClip")
    if logger.handlers:
        existing_path = getattr(logger, "_dynaclip_log_dir", None)
        return logger, existing_path

    logger.setLevel(logging.INFO)
    logger.propagate = False
    log_dir = None
    try:
        log_dir = get_app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "dynaclip.log",
            maxBytes=256 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger._dynaclip_log_dir = log_dir
    except Exception:
        logger.addHandler(logging.NullHandler())
    return logger, log_dir


def get_resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return base.joinpath(*parts)


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]


class ClipboardItem:
    __slots__ = ("id", "kind", "payload", "timestamp", "fingerprint")

    def __init__(self, item_id: int, kind: str, payload):
        self.id = item_id
        self.kind = kind
        self.payload = payload
        self.timestamp = datetime.now()
        self.fingerprint = self._build_fingerprint()

    def _build_fingerprint(self) -> str:
        if self.kind == "text":
            content = self.payload or ""
        elif self.kind == "files":
            content = "\n".join(self.payload)
        elif self.kind == "image":
            content = hashlib.sha1(self.payload).hexdigest()
        else:
            content = str(self.payload)
        return f"{self.kind}:{content}"

    @property
    def text(self) -> str:
        if self.kind == "text":
            return self.payload
        if self.kind == "files":
            count = len(self.payload)
            noun = "file" if count == 1 else "files"
            return f"{count} {noun}\n" + "\n".join(self.payload)
        if self.kind == "image":
            return f"Bitmap image ({len(self.payload)} bytes)"
        return ""

    @property
    def kind_label(self) -> str:
        if self.kind == "text":
            return "Text"
        if self.kind == "files":
            return "Files"
        if self.kind == "image":
            return "Image"
        return "Data"

    @property
    def display_text(self) -> str:
        if self.kind == "files":
            count = len(self.payload)
            first = Path(self.payload[0]).name if self.payload else "files"
            label = f"{first} (+{count - 1})" if count > 1 else first
            return f"[{self.kind_label}] {label}"
        if self.kind == "image":
            return f"[{self.kind_label}] Bitmap image"
        if not self.text:
            return "(empty)"
        single_line = (
            self.text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()
        )
        prefix = f"[{self.kind_label}] " if self.kind != "text" else ""
        display = single_line[:44] + "..." if len(single_line) > 44 else single_line
        return prefix + display

    @property
    def formatted_timestamp(self) -> str:
        return self.timestamp.strftime("%H:%M")


class ModernTheme:
    def __init__(self):
        self.is_dark = self._detect_dark_mode()

        if self.is_dark:
            self.bg_primary = "#0a0a0a"
            self.bg_secondary = "#171717"
            self.bg_card = "#1c1c1c"
            self.bg_card_hover = "#262626"
            self.fg_primary = "#fafafa"
            self.fg_secondary = "#a1a1aa"
            self.fg_muted = "#6a7282"
            self.accent = "#79c0ff"
            self.accent_secondary = "#5eb1ff"
            self.accent_dark = "#1772e7"
            self.accent_glow = "#0f2032"
            self.border = "#2b2b2b"
            self.border_strong = "#3a3a3a"
            self.success = "#22c55e"
            self.warning = "#f59e0b"
            self.danger = "#ef4444"
            self.shadow = "#050505"
            self.surface_tint = "#101827"
        else:
            self.bg_primary = "#f8fbff"
            self.bg_secondary = "#ffffff"
            self.bg_card = "#ffffff"
            self.bg_card_hover = "#f2f4f9"
            self.fg_primary = "#020618"
            self.fg_secondary = "#62748e"
            self.fg_muted = "#8b949e"
            self.accent = "#1772e7"
            self.accent_secondary = "#5eb1ff"
            self.accent_dark = "#0c69bf"
            self.accent_glow = "#e8f4fc"
            self.border = "#e0e4ed"
            self.border_strong = "#d1d5dc"
            self.success = "#22c55e"
            self.warning = "#f59e0b"
            self.danger = "#ef4444"
            self.shadow = "#d8dee8"
            self.surface_tint = "#edf5ff"

    def _detect_dark_mode(self) -> bool:
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0
        except Exception:
            return True


class DynaClip:
    TRIGGER_ZONE = 5
    HIDE_DELAY = 900
    EXPANDED_HIDE_DELAY = 650
    MAX_ITEMS = 50
    ANIM_STEPS = 12
    ANIM_INTERVAL = 14

    PILL_WIDTH = 168
    PILL_HEIGHT = 38
    PILL_RADIUS = 38
    EXPANDED_WIDTH = 980
    EXPANDED_HEIGHT = 94
    EXPANDED_RADIUS = 28
    TOP_MARGIN = 8
    GLOW_PAD_COMPACT = 1
    GLOW_PAD_EXPANDED = 6
    POINTER_POLL_INTERVAL = 90

    STATE_HIDDEN = "hidden"
    STATE_COMPACT = "compact"
    STATE_EXPANDED = "expanded"

    def __init__(self, mutex_handle=None):
        self.theme = ModernTheme()
        self.mutex_handle = mutex_handle
        self.logger, self.log_dir = setup_logger()
        self.items = []
        self.next_id = 1
        self.allow_duplicates = True
        self.auto_capture = False
        self.run_at_startup = False
        self.last_clipboard = ""
        self.mouse_in_window = False
        self.hide_timer = None
        self.status_timer = None
        self.mouse_after_id = None
        self.clipboard_after_id = None
        self.pointer_after_id = None
        self.hotkey_after_id = None
        self.animating = False
        self.pending_state = None
        self.state = self.STATE_HIDDEN
        self.search_var = None
        self.detail_windows = {}
        self.hotkey_registered = False
        self.tray_icon_added = False
        self.tray_hwnd = None
        self.tray_menu = None
        self.tray_wndproc = None
        self._old_tray_wndproc = None
        self.icon_path = get_resource_path("dynaclip.ico")
        self.tray_hicon = None

        self.work_left = 0
        self.work_top = 0
        self.work_width = 1920
        self.work_height = 1040
        self.monitor_top = 0

        self.current_x = 0
        self.current_y = 0
        self.current_width = self.PILL_WIDTH
        self.current_height = self.PILL_HEIGHT
        self.current_radius = self.PILL_RADIUS

        self.root = tk.Tk()
        self.root.title("DynaClip")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.98)
        self.root.configure(bg=self.theme.shadow)
        try:
            if self.icon_path.exists():
                self.root.iconbitmap(default=str(self.icon_path))
        except Exception:
            pass

        self._update_work_area()
        self._load_settings()
        self._set_geometry_for_state(self.STATE_HIDDEN)
        self.root.update_idletasks()
        self._configure_window_style()
        self._setup_ui()
        self._setup_clipboard_monitor()
        self._start_clipboard_polling()
        self._start_mouse_monitor()
        self._start_pointer_monitor()
        self._register_hotkey()
        self._create_tray_icon()
        self._apply_startup_setting()

        self.root.bind("<Enter>", self._on_window_enter)
        self.root.bind("<Leave>", self._on_window_leave)
        self.root.bind("<Escape>", lambda e: self._collapse_to_compact_or_hide())
        self.logger.info("app_started version=%s", APP_VERSION)

    def _configure_window_style(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            user32 = ctypes.windll.user32
            current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = (
                current_style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            ) & ~WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        except Exception:
            pass

    def _load_settings(self):
        try:
            import winreg

            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, SETTINGS_KEY)
            self.allow_duplicates = bool(
                int(winreg.QueryValueEx(key, "AllowDuplicates")[0])
            )
            self.auto_capture = bool(int(winreg.QueryValueEx(key, "AutoCapture")[0]))
            self.run_at_startup = bool(int(winreg.QueryValueEx(key, "RunAtStartup")[0]))
            winreg.CloseKey(key)
        except Exception:
            pass

    def _save_settings(self):
        try:
            import winreg

            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, SETTINGS_KEY)
            winreg.SetValueEx(
                key,
                "AllowDuplicates",
                0,
                winreg.REG_SZ,
                "1" if self.allow_duplicates else "0",
            )
            winreg.SetValueEx(
                key, "AutoCapture", 0, winreg.REG_SZ, "1" if self.auto_capture else "0"
            )
            winreg.SetValueEx(
                key,
                "RunAtStartup",
                0,
                winreg.REG_SZ,
                "1" if self.run_at_startup else "0",
            )
            winreg.CloseKey(key)
        except Exception as exc:
            self.logger.warning("settings_save_failed error=%s", exc.__class__.__name__)

    def _apply_startup_setting(self):
        try:
            import winreg

            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY)
            if self.run_at_startup:
                executable = sys.executable
                target = executable
                if executable.lower().endswith(
                    "python.exe"
                ) or executable.lower().endswith("pythonw.exe"):
                    target = f'"{executable}" "{Path(__file__).resolve()}"'
                else:
                    target = f'"{Path(executable).resolve()}"'
                winreg.SetValueEx(key, "DynaClip", 0, winreg.REG_SZ, target)
                self._write_startup_shortcut_fallback(target)
            else:
                try:
                    winreg.DeleteValue(key, "DynaClip")
                except FileNotFoundError:
                    pass
                self._remove_startup_shortcut_fallback()
            winreg.CloseKey(key)
        except Exception as exc:
            self.logger.warning(
                "startup_setting_failed error=%s", exc.__class__.__name__
            )

    def _startup_shortcut_path(self) -> Path:
        appdata = os.getenv("APPDATA")
        if appdata:
            return (
                Path(appdata)
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
                / "Startup"
                / "DynaClip.cmd"
            )
        return (
            Path.home()
            / "AppData"
            / "Roaming"
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
            / "DynaClip.cmd"
        )

    def _write_startup_shortcut_fallback(self, target: str):
        try:
            shortcut = self._startup_shortcut_path()
            shortcut.parent.mkdir(parents=True, exist_ok=True)
            shortcut.write_text(f'@echo off\r\nstart "" {target}\r\n', encoding="utf-8")
        except Exception as exc:
            self.logger.warning(
                "startup_shortcut_failed error=%s", exc.__class__.__name__
            )

    def _remove_startup_shortcut_fallback(self):
        try:
            shortcut = self._startup_shortcut_path()
            if shortcut.exists():
                shortcut.unlink()
        except Exception:
            pass

    def _register_hotkey(self):
        try:
            if ctypes.windll.user32.RegisterHotKey(
                None, HOTKEY_ID, HOTKEY_MODIFIERS, VK_SPACE
            ):
                self.hotkey_registered = True
                self.hotkey_after_id = self._safe_after(100, self._poll_hotkey)
        except Exception:
            self.hotkey_registered = False

    def _create_tray_icon(self):
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            window_class = "DynaClipTrayWindow"
            h_instance = kernel32.GetModuleHandleW(None)

            class WNDCLASS(ctypes.Structure):
                _fields_ = [
                    ("style", wintypes.UINT),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HCURSOR),
                    ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR),
                    ("lpszClassName", wintypes.LPCWSTR),
                ]

            self.tray_wndproc = WNDPROC(self._tray_wnd_proc)
            wndclass = WNDCLASS()
            wndclass.lpfnWndProc = self.tray_wndproc
            wndclass.lpszClassName = window_class
            wndclass.hInstance = h_instance
            if self.icon_path.exists():
                self.tray_hicon = user32.LoadImageW(
                    None,
                    str(self.icon_path),
                    IMAGE_ICON,
                    0,
                    0,
                    LR_LOADFROMFILE | LR_DEFAULTSIZE,
                )
            wndclass.hIcon = self.tray_hicon or user32.LoadIconW(
                None, ctypes.c_wchar_p(IDI_APPLICATION)
            )
            try:
                user32.RegisterClassW(ctypes.byref(wndclass))
            except Exception:
                pass

            self.tray_hwnd = user32.CreateWindowExW(
                0,
                window_class,
                "DynaClipTray",
                0,
                0,
                0,
                0,
                0,
                None,
                None,
                h_instance,
                None,
            )
            if not self.tray_hwnd:
                return

            class NOTIFYICONDATA(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("hWnd", wintypes.HWND),
                    ("uID", wintypes.UINT),
                    ("uFlags", wintypes.UINT),
                    ("uCallbackMessage", wintypes.UINT),
                    ("hIcon", wintypes.HICON),
                    ("szTip", wintypes.WCHAR * 128),
                ]

            nid = NOTIFYICONDATA()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
            nid.hWnd = self.tray_hwnd
            nid.uID = TRAY_UID
            nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
            nid.uCallbackMessage = TRAY_CALLBACK_MSG
            nid.hIcon = self.tray_hicon or user32.LoadIconW(
                None, ctypes.c_wchar_p(IDI_APPLICATION)
            )
            nid.szTip = f"DynaClip {APP_VERSION}"
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
            self.tray_icon_added = True
        except Exception as exc:
            self.logger.warning("tray_create_failed error=%s", exc.__class__.__name__)

    def _show_tray_menu(self):
        try:
            user32 = ctypes.windll.user32
            self.tray_menu = user32.CreatePopupMenu()
            user32.AppendMenuW(self.tray_menu, 0x0000, 1001, "Open")
            user32.AppendMenuW(self.tray_menu, 0x0000, 1002, "Toggle Auto Capture")
            user32.AppendMenuW(self.tray_menu, 0x0000, 1003, "Toggle Startup")
            user32.AppendMenuW(self.tray_menu, 0x0800, 0, None)
            user32.AppendMenuW(self.tray_menu, 0x0000, 1004, "Exit")
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(self.tray_hwnd)
            command = user32.TrackPopupMenu(
                self.tray_menu,
                0x0100 | 0x0002,
                pt.x,
                pt.y,
                0,
                self.tray_hwnd,
                None,
            )
            if command == 1001:
                self._show_compact()
                self._expand()
            elif command == 1002:
                self._toggle_auto_capture()
            elif command == 1003:
                self._toggle_startup()
            elif command == 1004:
                self._quit_app()
            user32.DestroyMenu(self.tray_menu)
            self.tray_menu = None
        except Exception as exc:
            self.logger.warning("tray_menu_failed error=%s", exc.__class__.__name__)

    def _tray_wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == TRAY_CALLBACK_MSG:
            if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self.root.after(0, self._toggle_visibility)
                return 0
            if lparam in (WM_RBUTTONUP, WM_CONTEXTMENU):
                self.root.after(0, self._show_tray_menu)
                return 0
        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _poll_hotkey(self):
        try:
            msg = wintypes.MSG()
            PM_REMOVE = 0x0001
            while ctypes.windll.user32.PeekMessageW(
                ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE
            ):
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self._toggle_visibility()
        except Exception:
            pass
        self.hotkey_after_id = self._safe_after(100, self._poll_hotkey)

    def _update_work_area_for_point(self, x: int, y: int):
        try:
            user32 = ctypes.windll.user32
            pt = POINT(x, y)
            h_monitor = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(h_monitor, ctypes.byref(mi))
            self.work_left = mi.rcWork.left
            self.work_top = mi.rcWork.top
            self.work_width = mi.rcWork.right - mi.rcWork.left
            self.work_height = mi.rcWork.bottom - mi.rcWork.top
            self.monitor_top = mi.rcMonitor.top
        except Exception:
            self.work_left = 0
            self.work_top = 0
            self.work_width = 1920
            self.work_height = 1040
            self.monitor_top = 0

    def _update_work_area(self):
        self._update_work_area_for_point(0, 0)

    def _centered_x(self, width: int) -> int:
        return self.work_left + max((self.work_width - width) // 2, 0)

    def _glow_pad_for_state(self, state: str) -> int:
        return (
            self.GLOW_PAD_EXPANDED
            if state == self.STATE_EXPANDED
            else self.GLOW_PAD_COMPACT
        )

    def _apply_visual_chrome(self, state: str, glow_pad=None):
        if glow_pad is None:
            glow_pad = self._glow_pad_for_state(state)
        glow_color = (
            self.theme.accent_glow
            if state == self.STATE_EXPANDED
            else self.theme.shadow
        )
        self.outer_glow.config(bg=glow_color)
        self.shell_border.pack_configure(padx=glow_pad, pady=glow_pad)

    def _target_bounds_for_state(self, state: str):
        if state == self.STATE_EXPANDED:
            width = min(self.EXPANDED_WIDTH, self.work_width - 40)
            height = self.EXPANDED_HEIGHT
            radius = self.EXPANDED_RADIUS
            x = self._centered_x(width)
            y = self.work_top + self.TOP_MARGIN
        elif state == self.STATE_COMPACT:
            width = self.PILL_WIDTH
            height = self.PILL_HEIGHT
            radius = self.PILL_RADIUS
            x = self._centered_x(width)
            y = self.work_top + self.TOP_MARGIN
        else:
            width = self.PILL_WIDTH
            height = self.PILL_HEIGHT
            radius = self.PILL_RADIUS
            x = self._centered_x(width)
            y = self.work_top - height + 6
        return x, y, width, height, radius

    def _apply_round_region(self, width: int, height: int, radius: int):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            gdi32 = ctypes.windll.gdi32
            user32 = ctypes.windll.user32
            region = gdi32.CreateRoundRectRgn(
                0, 0, width + 1, height + 1, radius, radius
            )
            user32.SetWindowRgn(hwnd, region, True)
        except Exception:
            pass

    def _apply_geometry(self, x: int, y: int, width: int, height: int, radius: int):
        self.current_x = x
        self.current_y = y
        self.current_width = width
        self.current_height = height
        self.current_radius = radius
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.update_idletasks()
        self._apply_round_region(width, height, radius)

    def _safe_after(self, delay, callback):
        def wrapped():
            try:
                callback()
            except Exception:
                pass

        return self.root.after(delay, wrapped)

    def _set_geometry_for_state(self, state: str):
        x, y, width, height, radius = self._target_bounds_for_state(state)
        self._apply_geometry(x, y, width, height, radius)
        self.state = state
        self._apply_visual_chrome(state)
        self._sync_layout_for_state()

    def _ease_out_back(self, t: float) -> float:
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

    def _animate_to_state(self, target_state: str):
        if self.animating:
            self.pending_state = target_state
            return
        if target_state == self.state:
            return
        self.animating = True
        start = (
            self.current_x,
            self.current_y,
            self.current_width,
            self.current_height,
            self.current_radius,
        )
        end = self._target_bounds_for_state(target_state)
        step = [0]
        self.pending_state = None

        if target_state == self.STATE_EXPANDED:
            center_x = start[0] + start[2] // 2
            center_y = start[1] + start[3] // 2
            start_width = max(int(start[2] * 0.92), start[2] - 12)
            start_height = max(int(start[3] * 0.9), start[3] - 6)
            start_radius = max(start[4] - 4, self.EXPANDED_RADIUS)
            start = (
                center_x - start_width // 2,
                center_y - start_height // 2,
                start_width,
                start_height,
                start_radius,
            )

        if target_state == self.STATE_EXPANDED:
            self.expanded_shell.pack(fill="both", expand=True)
            self.compact_shell.place_forget()
        elif target_state == self.STATE_COMPACT:
            self.compact_shell.place(relx=0.5, rely=0.5, anchor="center")

        start_glow = self._glow_pad_for_state(self.state)
        end_glow = self._glow_pad_for_state(target_state)
        self._apply_visual_chrome(
            target_state if target_state == self.STATE_EXPANDED else self.state,
            start_glow,
        )

        def tick():
            step[0] += 1
            t = min(step[0] / self.ANIM_STEPS, 1.0)
            if target_state == self.STATE_EXPANDED or (
                target_state == self.STATE_COMPACT and self.state == self.STATE_HIDDEN
            ):
                eased = self._ease_out_back(t)
            else:
                eased = 1 - (1 - t) ** 3
            x = int(start[0] + (end[0] - start[0]) * eased)
            y = int(start[1] + (end[1] - start[1]) * eased)
            width = int(start[2] + (end[2] - start[2]) * eased)
            height = int(start[3] + (end[3] - start[3]) * eased)
            radius = int(start[4] + (end[4] - start[4]) * eased)
            glow_pad = int(start_glow + (end_glow - start_glow) * min(max(t, 0.0), 1.0))
            self._apply_geometry(x, y, width, height, radius)
            self._apply_visual_chrome(target_state, glow_pad)
            if t < 1.0:
                self.root.after(self.ANIM_INTERVAL, tick)
            else:
                self.animating = False
                self.state = target_state
                self._apply_visual_chrome(target_state)
                self._sync_layout_for_state()
                if self.pending_state and self.pending_state != self.state:
                    next_state = self.pending_state
                    self.pending_state = None
                    self._animate_to_state(next_state)

        tick()

    def _sync_layout_for_state(self):
        if self.state == self.STATE_EXPANDED:
            self.compact_shell.place_forget()
            self.expanded_shell.pack(fill="both", expand=True)
            self.outer_glow.config(bg=self.theme.shadow)
            self.inner_surface.config(bg=self.theme.bg_primary)
            self.status_frame.pack(side="right", fill="y")
            self._refresh_items()
        elif self.state == self.STATE_COMPACT:
            self.expanded_shell.pack_forget()
            self.compact_shell.place(relx=0.5, rely=0.5, anchor="center")
            self.outer_glow.config(bg=self.theme.shadow)
            self.inner_surface.config(bg=self.theme.bg_primary)
            self._refresh_compact_pill()
        else:
            self.expanded_shell.pack_forget()
            self.compact_shell.place_forget()

    def _setup_ui(self):
        self.outer_glow = tk.Frame(self.root, bg=self.theme.shadow)
        self.outer_glow.pack(fill="both", expand=True)

        self.shell_border = tk.Frame(self.outer_glow, bg=self.theme.border_strong)
        self.shell_border.pack(fill="both", expand=True, padx=1, pady=1)

        self.inner_surface = tk.Frame(self.shell_border, bg=self.theme.bg_primary)
        self.inner_surface.pack(fill="both", expand=True, padx=1, pady=1)

        self.compact_shell = tk.Frame(self.inner_surface, bg=self.theme.bg_primary)
        self.compact_shell.bind("<Button-1>", lambda e: self._expand())

        compact_inner = tk.Frame(self.compact_shell, bg=self.theme.bg_primary)
        compact_inner.pack(padx=14, pady=8)

        self.compact_icon = tk.Label(
            compact_inner,
            text="[]",
            font=("Segoe UI Symbol", 10),
            bg=self.theme.bg_primary,
            fg=self.theme.accent,
            cursor="hand2",
        )
        self.compact_icon.pack(side="left")
        self.compact_icon.bind("<Button-1>", lambda e: self._expand())

        self.compact_title = tk.Label(
            compact_inner,
            text="DynaClip",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme.bg_primary,
            fg=self.theme.fg_primary,
            cursor="hand2",
        )
        self.compact_title.pack(side="left", padx=(8, 8))
        self.compact_title.bind("<Button-1>", lambda e: self._expand())

        self.compact_badge = tk.Label(
            compact_inner,
            text="0",
            font=("Segoe UI", 8, "bold"),
            bg=self.theme.accent_glow,
            fg=self.theme.accent,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.compact_badge.pack(side="left")
        self.compact_badge.bind("<Button-1>", lambda e: self._expand())

        self.expanded_shell = tk.Frame(self.inner_surface, bg=self.theme.bg_primary)

        content = tk.Frame(self.expanded_shell, bg=self.theme.bg_primary)
        content.pack(fill="both", expand=True, padx=18, pady=10)

        left_frame = tk.Frame(content, bg=self.theme.bg_primary)
        left_frame.pack(side="left", fill="y")

        logo_frame = tk.Frame(left_frame, bg=self.theme.bg_primary)
        logo_frame.pack(side="left", padx=(0, 14))

        icon_label = tk.Label(
            logo_frame,
            text="[]",
            font=("Segoe UI Symbol", 12),
            bg=self.theme.bg_primary,
            fg=self.theme.accent,
        )
        icon_label.pack(side="left")

        title_label = tk.Label(
            logo_frame,
            text="DynaClip",
            font=("Segoe UI", 12, "bold"),
            bg=self.theme.bg_primary,
            fg=self.theme.fg_primary,
        )
        title_label.pack(side="left", padx=(6, 0))

        sep = tk.Frame(left_frame, bg=self.theme.border_strong, width=1)
        sep.pack(side="left", fill="y", padx=14, pady=8)

        btn_frame = tk.Frame(left_frame, bg=self.theme.bg_primary)
        btn_frame.pack(side="left")

        self.add_btn = self._create_pill_button(
            btn_frame, "+ Add", self.add_from_clipboard, primary=True
        )
        self.add_btn.pack(side="left", padx=(0, 8))

        self.menu_btn = self._create_icon_button(btn_frame, "O", self._show_menu)
        self.menu_btn.pack(side="left", padx=(0, 8))

        self.search_outer = tk.Frame(left_frame, bg=self.theme.border)
        self.search_outer.pack(side="left", padx=(8, 0))

        search_container = tk.Frame(self.search_outer, bg=self.theme.bg_secondary)
        search_container.pack(fill="both", expand=True, padx=1, pady=1)

        search_inner = tk.Frame(search_container, bg=self.theme.bg_secondary)
        search_inner.pack(fill="both", expand=True, padx=12, pady=5)

        search_icon = tk.Label(
            search_inner,
            text="?",
            font=("Segoe UI", 9, "bold"),
            bg=self.theme.bg_secondary,
            fg=self.theme.fg_muted,
        )
        search_icon.pack(side="left")

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_inner,
            textvariable=self.search_var,
            font=("Segoe UI", 10),
            width=14,
            bg=self.theme.bg_secondary,
            fg=self.theme.fg_primary,
            insertbackground=self.theme.accent,
            relief="flat",
            bd=0,
        )
        self.search_entry.pack(side="left", padx=(6, 0))
        self.search_entry.insert(0, "Search...")
        self.search_entry.config(fg=self.theme.fg_muted)
        self.search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)
        self.search_entry.bind(
            "<Escape>", lambda e: self._collapse_to_compact_or_hide()
        )
        self.search_entry.bind("<Control-a>", self._select_all_search)

        items_outer = tk.Frame(content, bg=self.theme.bg_primary)
        items_outer.pack(side="left", fill="both", expand=True, padx=(18, 8))

        self.canvas = tk.Canvas(
            items_outer,
            bg=self.theme.bg_primary,
            highlightthickness=0,
            height=54,
        )
        self.canvas.pack(side="top", fill="both", expand=True)

        self.items_container = tk.Frame(self.canvas, bg=self.theme.bg_primary)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.items_container, anchor="nw"
        )
        self.items_container.bind("<Configure>", self._on_items_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.empty_label = tk.Label(
            items_outer,
            text="No clips yet - copy something and click Add",
            font=("Segoe UI", 10),
            bg=self.theme.bg_primary,
            fg=self.theme.fg_muted,
        )

        self.status_frame = tk.Frame(content, bg=self.theme.bg_primary)

        self.status_label = tk.Label(
            self.status_frame,
            text="",
            font=("Segoe UI", 9, "bold"),
            bg=self.theme.bg_primary,
            fg=self.theme.success,
        )
        self.status_label.pack(side="right", pady=2)

        self.count_label = tk.Label(
            self.status_frame,
            text="0 items",
            font=("Segoe UI", 9),
            bg=self.theme.bg_primary,
            fg=self.theme.fg_muted,
        )
        self.count_label.pack(side="right", padx=(0, 12))

        self.search_var.trace_add("write", lambda *args: self._refresh_items())
        self._sync_layout_for_state()

    def _create_pill_button(self, parent, text, command, primary=False):
        bg = self.theme.accent_dark if primary else self.theme.bg_secondary
        fg = "#ffffff" if primary else self.theme.fg_primary
        hover_bg = self.theme.accent if primary else self.theme.bg_card_hover
        hover_fg = "#000000" if primary else self.theme.fg_primary

        btn = tk.Label(
            parent,
            text=text,
            font=("Segoe UI", 9, "bold"),
            bg=bg,
            fg=fg,
            cursor="hand2",
            padx=14,
            pady=5,
        )
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg, fg=hover_fg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg, fg=fg))
        return btn

    def _create_icon_button(self, parent, icon, command):
        btn = tk.Label(
            parent,
            text=icon,
            font=("Segoe UI", 10, "bold"),
            bg=self.theme.bg_primary,
            fg=self.theme.fg_muted,
            cursor="hand2",
            padx=8,
            pady=4,
        )
        btn.bind("<Button-1>", lambda e: command())
        btn.bind(
            "<Enter>",
            lambda e: btn.config(bg=self.theme.bg_secondary, fg=self.theme.accent),
        )
        btn.bind(
            "<Leave>",
            lambda e: btn.config(bg=self.theme.bg_primary, fg=self.theme.fg_muted),
        )
        return btn

    def _refresh_compact_pill(self):
        self.compact_badge.config(text=str(len(self.items)))

    def _select_all_search(self, event):
        self.search_entry.select_range(0, "end")
        self.search_entry.icursor("end")
        return "break"

    def _focus_search(self, _event=None):
        if self.state != self.STATE_EXPANDED:
            return "break"
        self.search_entry.focus_set()
        if self.search_entry.get() == "Search...":
            self.search_entry.delete(0, "end")
            self.search_entry.config(fg=self.theme.fg_primary)
        self.search_entry.select_range(0, "end")
        return "break"

    def _on_search_focus_in(self, event):
        if self.search_entry.get() == "Search...":
            self.search_entry.delete(0, "end")
            self.search_entry.config(fg=self.theme.fg_primary)
        self.search_outer.config(bg=self.theme.accent)

    def _on_search_focus_out(self, event):
        if not self.search_entry.get():
            self.search_entry.insert(0, "Search...")
            self.search_entry.config(fg=self.theme.fg_muted)
        self.search_outer.config(bg=self.theme.border)

    def _on_items_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, height=event.height)

    def _on_mousewheel(self, event):
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_window_enter(self, event):
        self.mouse_in_window = True
        if self.hide_timer:
            self.root.after_cancel(self.hide_timer)
            self.hide_timer = None

    def _on_window_leave(self, event):
        self.mouse_in_window = False
        delay = (
            self.EXPANDED_HIDE_DELAY
            if self.state == self.STATE_EXPANDED
            else self.HIDE_DELAY
        )
        self._schedule_hide(delay)

    def _schedule_hide(self, delay):
        if self.hide_timer:
            self.root.after_cancel(self.hide_timer)
        self.hide_timer = self._safe_after(delay, self._check_and_hide)

    def _check_and_hide(self):
        if not self._is_pointer_inside_any_window():
            self._collapse_to_compact_or_hide()
        self.hide_timer = None

    def _is_pointer_inside_window(self, window):
        try:
            if not window.winfo_exists():
                return False
            x_pos, y_pos = window.winfo_pointerxy()
            wx = window.winfo_rootx()
            wy = window.winfo_rooty()
            ww = window.winfo_width()
            wh = window.winfo_height()
            return wx <= x_pos < wx + ww and wy <= y_pos < wy + wh
        except Exception:
            return False

    def _is_pointer_inside_any_window(self):
        if self._is_pointer_inside_window(self.root):
            return True
        for window in list(self.detail_windows.values()):
            if self._is_pointer_inside_window(window):
                return True
        return False

    def _start_pointer_monitor(self):
        def poll():
            try:
                self.mouse_in_window = self._is_pointer_inside_any_window()
            except Exception:
                pass
            self.pointer_after_id = self._safe_after(self.POINTER_POLL_INTERVAL, poll)

        self.pointer_after_id = self._safe_after(self.POINTER_POLL_INTERVAL, poll)

    def _show_compact(self, mouse_x=0, mouse_y=0):
        if mouse_x or mouse_y:
            self._update_work_area_for_point(mouse_x, mouse_y)
        if self.hide_timer:
            self.root.after_cancel(self.hide_timer)
            self.hide_timer = None
        self.root.lift()
        if self.state == self.STATE_HIDDEN:
            self._animate_to_state(self.STATE_COMPACT)

    def _expand(self):
        if self.state != self.STATE_EXPANDED:
            if self.hide_timer:
                self.root.after_cancel(self.hide_timer)
                self.hide_timer = None
            self.root.lift()
            if self.state == self.STATE_HIDDEN:
                self._set_geometry_for_state(self.STATE_COMPACT)
            self._animate_to_state(self.STATE_EXPANDED)

    def _toggle_visibility(self):
        if self.state == self.STATE_HIDDEN:
            self._show_compact()
        elif self.state == self.STATE_COMPACT:
            self._expand()
        else:
            self._collapse_to_compact_or_hide()

    def _collapse_to_compact_or_hide(self):
        if self.animating:
            return
        if self.state == self.STATE_EXPANDED:
            self._animate_to_state(self.STATE_COMPACT)
            self._schedule_hide(self.HIDE_DELAY)
        elif self.state == self.STATE_COMPACT:
            self._animate_to_state(self.STATE_HIDDEN)

    def _quit_app(self):
        if self.tray_icon_added and self.tray_hwnd:
            try:

                class NOTIFYICONDATA(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("hWnd", wintypes.HWND),
                        ("uID", wintypes.UINT),
                        ("uFlags", wintypes.UINT),
                        ("uCallbackMessage", wintypes.UINT),
                        ("hIcon", wintypes.HICON),
                        ("szTip", wintypes.WCHAR * 128),
                    ]

                nid = NOTIFYICONDATA()
                nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
                nid.hWnd = self.tray_hwnd
                nid.uID = TRAY_UID
                ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            except Exception:
                pass
            self.tray_icon_added = False
        for after_id in [
            self.hide_timer,
            self.status_timer,
            self.mouse_after_id,
            self.clipboard_after_id,
            self.pointer_after_id,
            self.hotkey_after_id,
        ]:
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
        self.hide_timer = None
        self.status_timer = None
        self.mouse_after_id = None
        self.clipboard_after_id = None
        self.pointer_after_id = None
        self.hotkey_after_id = None
        if self.hotkey_registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            except Exception:
                pass
            self.hotkey_registered = False
        for window in list(self.detail_windows.values()):
            try:
                window.destroy()
            except Exception:
                pass
        self.detail_windows.clear()
        if self.tray_hwnd:
            try:
                ctypes.windll.user32.DestroyWindow(self.tray_hwnd)
            except Exception:
                pass
            self.tray_hwnd = None
        if self.tray_hicon:
            try:
                ctypes.windll.user32.DestroyIcon(self.tray_hicon)
            except Exception:
                pass
            self.tray_hicon = None
        if self.mutex_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
            except Exception:
                pass
            self.mutex_handle = None
        try:
            self.root.destroy()
        except Exception:
            pass

    def _start_mouse_monitor(self):
        user32 = ctypes.windll.user32
        pt = POINT()

        def monitor():
            try:
                user32.GetCursorPos(ctypes.byref(pt))
                h_monitor = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                user32.GetMonitorInfoW(h_monitor, ctypes.byref(mi))
                monitor_top = mi.rcMonitor.top
                if pt.y <= monitor_top + self.TRIGGER_ZONE:
                    if self.state == self.STATE_HIDDEN:
                        self._show_compact(pt.x, pt.y)
            except Exception:
                pass
            self.mouse_after_id = self._safe_after(50, monitor)

        self.mouse_after_id = self._safe_after(120, monitor)

    def _show_menu(self):
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=self.theme.bg_card,
            fg=self.theme.fg_primary,
            activebackground=self.theme.accent_dark,
            activeforeground="#ffffff",
            font=("Segoe UI", 10),
            bd=0,
            relief="flat",
        )
        menu.add_command(label="  Clear All", command=self._clear_history)
        menu.add_command(
            label=(
                "  [x] Allow Duplicates"
                if self.allow_duplicates
                else "  [ ] Allow Duplicates"
            ),
            command=self._toggle_duplicates,
        )
        menu.add_command(
            label=("  [x] Auto Capture" if self.auto_capture else "  [ ] Auto Capture"),
            command=self._toggle_auto_capture,
        )
        menu.add_command(
            label=(
                "  [x] Run at Startup"
                if self.run_at_startup
                else "  [ ] Run at Startup"
            ),
            command=self._toggle_startup,
        )
        menu.add_separator()
        menu.add_command(label=f"  {len(self.items)} items in memory")
        menu.add_command(label=f"  {HOTKEY_LABEL} toggle hotkey")
        menu.add_separator()
        menu.add_command(label="  Exit", command=self._quit_app)
        x = self.menu_btn.winfo_rootx()
        y = self.menu_btn.winfo_rooty() + self.menu_btn.winfo_height() + 6
        menu.post(x, y)

    def _clear_history(self):
        if messagebox.askyesno("Clear History", "Clear all clipboard history?"):
            self.items.clear()
            self.next_id = 1
            self._refresh_items()
            self._set_status("History cleared")

    def _toggle_duplicates(self):
        self.allow_duplicates = not self.allow_duplicates
        self._save_settings()
        self._set_status("Duplicates on" if self.allow_duplicates else "Duplicates off")

    def _toggle_auto_capture(self):
        self.auto_capture = not self.auto_capture
        self._save_settings()
        self._set_status("Auto capture on" if self.auto_capture else "Auto capture off")

    def _toggle_startup(self):
        self.run_at_startup = not self.run_at_startup
        self._save_settings()
        self._apply_startup_setting()
        self._set_status("Startup on" if self.run_at_startup else "Startup off")

    def _read_clipboard_item(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32

        if not user32.OpenClipboard(None):
            return None
        try:
            if user32.IsClipboardFormatAvailable(CF_HDROP):
                handle = user32.GetClipboardData(CF_HDROP)
                if handle:
                    count = shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
                    files = []
                    for index in range(count):
                        length = shell32.DragQueryFileW(handle, index, None, 0) + 1
                        buffer = ctypes.create_unicode_buffer(length)
                        shell32.DragQueryFileW(handle, index, buffer, length)
                        files.append(buffer.value)
                    if files:
                        return "files", files

            if user32.IsClipboardFormatAvailable(CF_DIB):
                handle = user32.GetClipboardData(CF_DIB)
                if handle:
                    size = kernel32.GlobalSize(handle)
                    pointer = kernel32.GlobalLock(handle)
                    if pointer and size:
                        data = ctypes.string_at(pointer, size)
                        kernel32.GlobalUnlock(handle)
                        return "image", data

            if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if handle:
                    pointer = kernel32.GlobalLock(handle)
                    if pointer:
                        text = ctypes.wstring_at(pointer)
                        kernel32.GlobalUnlock(handle)
                        return "text", text
        finally:
            user32.CloseClipboard()
        return None

    def _copy_files_to_clipboard(self, files):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        payload = "\0".join(files) + "\0\0"
        payload_bytes = payload.encode("utf-16le")
        structure = DROPFILES()
        structure.pFiles = ctypes.sizeof(DROPFILES)
        structure.fWide = True
        total_size = ctypes.sizeof(DROPFILES) + len(payload_bytes)

        h_global = kernel32.GlobalAlloc(GHND, total_size)
        if not h_global:
            raise RuntimeError("GlobalAlloc failed")
        pointer = kernel32.GlobalLock(h_global)
        if not pointer:
            kernel32.GlobalFree(h_global)
            raise RuntimeError("GlobalLock failed")
        try:
            ctypes.memmove(pointer, ctypes.byref(structure), ctypes.sizeof(DROPFILES))
            ctypes.memmove(
                pointer + ctypes.sizeof(DROPFILES), payload_bytes, len(payload_bytes)
            )
        finally:
            kernel32.GlobalUnlock(h_global)

        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(h_global)
            raise RuntimeError("OpenClipboard failed")
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(CF_HDROP, h_global):
                kernel32.GlobalFree(h_global)
                raise RuntimeError("SetClipboardData failed")
        finally:
            user32.CloseClipboard()

    def _copy_image_to_clipboard(self, dib_bytes):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        h_global = kernel32.GlobalAlloc(GHND, len(dib_bytes))
        if not h_global:
            raise RuntimeError("GlobalAlloc failed")
        pointer = kernel32.GlobalLock(h_global)
        if not pointer:
            kernel32.GlobalFree(h_global)
            raise RuntimeError("GlobalLock failed")
        try:
            ctypes.memmove(pointer, dib_bytes, len(dib_bytes))
        finally:
            kernel32.GlobalUnlock(h_global)

        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(h_global)
            raise RuntimeError("OpenClipboard failed")
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(CF_DIB, h_global):
                kernel32.GlobalFree(h_global)
                raise RuntimeError("SetClipboardData failed")
        finally:
            user32.CloseClipboard()

    def _refresh_items(self):
        for widget in self.items_container.winfo_children():
            widget.destroy()

        search = self.search_var.get() if self.search_var else ""
        if search == "Search...":
            search = ""

        filtered = [
            item
            for item in self.items
            if not search
            or search.lower() in item.text.lower()
            or search.lower() in item.kind_label.lower()
        ]

        if not filtered:
            self.empty_label.pack(expand=True, fill="both")
            self.canvas.pack_forget()
        else:
            self.empty_label.pack_forget()
            self.canvas.pack(side="top", fill="both", expand=True)
            for item in filtered:
                self._create_item_widget(item)

        self.count_label.config(text=f"{len(self.items)} items")
        self._refresh_compact_pill()

    def _create_item_widget(self, item: ClipboardItem):
        outer = tk.Frame(self.items_container, bg=self.theme.border)
        outer.pack(side="left", fill="y", padx=4, pady=5)

        card = tk.Frame(outer, bg=self.theme.bg_card, cursor="hand2")
        card.pack(fill="both", expand=True, padx=1, pady=1)

        inner = tk.Frame(card, bg=self.theme.bg_card)
        inner.pack(fill="both", expand=True, padx=13, pady=8)

        text_label = tk.Label(
            inner,
            text=item.display_text,
            font=("Segoe UI", 10),
            bg=self.theme.bg_card,
            fg=self.theme.fg_primary,
            anchor="w",
        )
        text_label.pack(side="left")

        time_label = tk.Label(
            inner,
            text=item.formatted_timestamp,
            font=("Segoe UI", 8),
            bg=self.theme.accent_glow,
            fg=self.theme.accent,
            padx=6,
            pady=1,
        )
        time_label.pack(side="left", padx=(10, 0))

        del_btn = tk.Label(
            inner,
            text="x",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme.bg_card,
            fg=self.theme.fg_muted,
            cursor="hand2",
            padx=5,
        )
        del_btn.pack(side="left", padx=(8, 0))

        hover = {"active": False}

        def apply_hover():
            outer.config(bg=self.theme.accent)
            card.config(bg=self.theme.bg_card_hover)
            inner.config(bg=self.theme.bg_card_hover)
            text_label.config(bg=self.theme.bg_card_hover)
            del_btn.config(bg=self.theme.bg_card_hover)

        def remove_hover():
            outer.config(bg=self.theme.border)
            card.config(bg=self.theme.bg_card)
            inner.config(bg=self.theme.bg_card)
            text_label.config(bg=self.theme.bg_card)
            del_btn.config(bg=self.theme.bg_card, fg=self.theme.fg_muted)

        def on_enter(_event):
            hover["active"] = True
            apply_hover()

        def on_leave(_event):
            x_pos, y_pos = outer.winfo_pointerxy()
            wx, wy = outer.winfo_rootx(), outer.winfo_rooty()
            ww, wh = outer.winfo_width(), outer.winfo_height()
            if not (wx <= x_pos < wx + ww and wy <= y_pos < wy + wh):
                hover["active"] = False
                remove_hover()

        def on_click(_event):
            self.copy_item(item)

        def on_open_detail(_event):
            self.open_detail_window(item)
            return "break"

        def on_del_enter(_event):
            del_btn.config(fg=self.theme.danger)
            apply_hover()

        def on_del_leave(_event):
            if hover["active"]:
                del_btn.config(fg=self.theme.fg_muted)

        def on_del_click(_event):
            self.delete_item(item.id)
            return "break"

        outer.bind("<Enter>", on_enter)
        outer.bind("<Leave>", on_leave)
        for widget in [card, inner, text_label, time_label]:
            widget.bind("<Button-1>", on_click)
            widget.bind("<Double-Button-1>", on_open_detail)
        del_btn.bind("<Enter>", on_del_enter)
        del_btn.bind("<Leave>", on_del_leave)
        del_btn.bind("<Button-1>", on_del_click)
        self._create_tooltip(outer, item.text)

    def open_detail_window(self, item: ClipboardItem):
        existing = self.detail_windows.get(item.id)
        if existing and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title(f"DynaClip - Clip {item.id}")
        window.configure(bg=self.theme.shadow)
        window.attributes("-topmost", True)
        window.geometry("720x480")
        window.minsize(520, 320)

        outer = tk.Frame(window, bg=self.theme.border_strong)
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        inner = tk.Frame(outer, bg=self.theme.bg_primary)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        header = tk.Frame(inner, bg=self.theme.bg_primary)
        header.pack(fill="x", padx=16, pady=(14, 10))

        title = tk.Label(
            header,
            text=item.display_text,
            font=("Segoe UI", 11, "bold"),
            bg=self.theme.bg_primary,
            fg=self.theme.fg_primary,
            anchor="w",
        )
        title.pack(side="left")

        meta = tk.Label(
            header,
            text=f"Clip #{item.id}  {item.kind_label}  {item.formatted_timestamp}",
            font=("Segoe UI", 9),
            bg=self.theme.bg_primary,
            fg=self.theme.fg_secondary,
            anchor="e",
        )
        meta.pack(side="right")

        toolbar = tk.Frame(inner, bg=self.theme.bg_primary)
        toolbar.pack(fill="x", padx=16, pady=(0, 10))

        copy_btn = self._create_pill_button(
            toolbar, "Copy", lambda: self.copy_item(item), primary=True
        )
        copy_btn.pack(side="left", padx=(0, 8))
        delete_btn = self._create_pill_button(
            toolbar,
            "Delete",
            lambda: self._delete_and_close_detail(item.id),
            primary=False,
        )
        delete_btn.pack(side="left", padx=(0, 8))

        text_outer = tk.Frame(inner, bg=self.theme.border)
        text_outer.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        text_frame = tk.Frame(text_outer, bg=self.theme.bg_secondary)
        text_frame.pack(fill="both", expand=True, padx=1, pady=1)

        text_widget = tk.Text(
            text_frame,
            wrap="word",
            font=("Consolas", 10),
            bg=self.theme.bg_secondary,
            fg=self.theme.fg_primary,
            insertbackground=self.theme.accent,
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
        )
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(text_frame, command=text_widget.yview)
        scrollbar.pack(side="right", fill="y")
        text_widget.config(yscrollcommand=scrollbar.set)
        if item.kind == "image":
            text_widget.insert(
                "1.0", f"Bitmap image in DIB format\n\nSize: {len(item.payload)} bytes"
            )
        else:
            text_widget.insert("1.0", item.text)
        text_widget.config(state="disabled")

        def on_close():
            self.detail_windows.pop(item.id, None)
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_close)
        self.detail_windows[item.id] = window

    def _delete_and_close_detail(self, item_id: int):
        window = self.detail_windows.pop(item_id, None)
        if window:
            try:
                window.destroy()
            except Exception:
                pass
        self.delete_item(item_id)

    def _create_tooltip(self, widget, text):
        tooltip = None
        tooltip_id = None

        def show_tooltip(_event):
            nonlocal tooltip, tooltip_id
            if tooltip_id:
                widget.after_cancel(tooltip_id)
                tooltip_id = None
            if tooltip:
                return

            def create():
                nonlocal tooltip
                if tooltip:
                    return
                x = widget.winfo_rootx() + 10
                y = widget.winfo_rooty() + widget.winfo_height() + 8
                tooltip = tk.Toplevel(widget)
                tooltip.wm_overrideredirect(True)
                tooltip.wm_geometry(f"+{x}+{y}")
                tooltip.attributes("-topmost", True)
                tooltip.configure(bg=self.theme.border_strong)
                inner = tk.Frame(tooltip, bg=self.theme.bg_card)
                inner.pack(fill="both", expand=True, padx=1, pady=1)
                accent = tk.Frame(inner, bg=self.theme.accent, height=2)
                accent.pack(side="top", fill="x")
                display = text[:500] + "..." if len(text) > 500 else text
                label = tk.Label(
                    inner,
                    text=display,
                    justify="left",
                    bg=self.theme.bg_card,
                    fg=self.theme.fg_primary,
                    font=("Segoe UI", 9),
                    wraplength=380,
                    padx=14,
                    pady=10,
                )
                label.pack()

            tooltip_id = widget.after(400, create)

        def hide_tooltip(_event):
            nonlocal tooltip, tooltip_id
            if tooltip_id:
                widget.after_cancel(tooltip_id)
                tooltip_id = None
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", show_tooltip, add="+")
        widget.bind("<Leave>", hide_tooltip, add="+")

    def add_from_clipboard(self):
        try:
            item_data = self._read_clipboard_item()
            if item_data:
                self.add_item(*item_data)
            else:
                self._set_status("Empty clipboard")
        except Exception:
            self._set_status("Unsupported clipboard")

    def add_item(self, kind: str, payload):
        if not payload:
            return

        incoming_fingerprint = ClipboardItem(-1, kind, payload).fingerprint

        if not self.allow_duplicates:
            for item in self.items:
                if item.fingerprint == incoming_fingerprint:
                    self.items.remove(item)
                    item.timestamp = datetime.now()
                    self.items.insert(0, item)
                    self._refresh_items()
                    self._set_status("Moved item to top")
                    self.logger.info("item_bumped_to_top")
                    return

        item = ClipboardItem(self.next_id, kind, payload)
        self.next_id += 1
        self.items.insert(0, item)
        if len(self.items) > self.MAX_ITEMS:
            self.items = self.items[: self.MAX_ITEMS]
        self._refresh_items()
        self._set_status("Added clip")
        self.logger.info("item_added count=%s", len(self.items))

    def copy_item(self, item: ClipboardItem):
        try:
            if item.kind == "text":
                self.root.clipboard_clear()
                self.root.clipboard_append(item.payload)
            elif item.kind == "files":
                self._copy_files_to_clipboard(item.payload)
            elif item.kind == "image":
                self._copy_image_to_clipboard(item.payload)
            self.last_clipboard = f"{item.kind}:{item.fingerprint}"
            self._set_status("Copied")
            self.logger.info("item_copied item_id=%s kind=%s", item.id, item.kind)
        except Exception as exc:
            self._set_status("Copy failed")
            self.logger.warning(
                "item_copy_failed item_id=%s error=%s", item.id, exc.__class__.__name__
            )

    def delete_item(self, item_id: int):
        detail = self.detail_windows.pop(item_id, None)
        if detail:
            try:
                detail.destroy()
            except Exception:
                pass
        self.items = [item for item in self.items if item.id != item_id]
        self._refresh_items()
        self._set_status("Deleted")
        self.logger.info("item_deleted item_id=%s count=%s", item_id, len(self.items))

    def _set_status(self, message: str):
        self.status_label.config(text=message)
        if "Copied" in message or "Added" in message:
            self.status_label.config(fg=self.theme.success)
        elif "Deleted" in message:
            self.status_label.config(fg=self.theme.danger)
        else:
            self.status_label.config(fg=self.theme.accent)
        if self.status_timer:
            try:
                self.root.after_cancel(self.status_timer)
            except Exception:
                pass
        self.status_timer = self.root.after(2200, self._clear_status)

    def _clear_status(self):
        self.status_label.config(text="")
        self.status_timer = None

    def _setup_clipboard_monitor(self):
        try:
            current = self._read_clipboard_item()
            if current:
                self.last_clipboard = f"{current[0]}:{ClipboardItem(-1, current[0], current[1]).fingerprint}"
            else:
                self.last_clipboard = ""
        except Exception:
            self.last_clipboard = ""

    def _start_clipboard_polling(self):
        def poll():
            try:
                current = self._read_clipboard_item()
                if current:
                    current_summary = f"{current[0]}:{ClipboardItem(-1, current[0], current[1]).fingerprint}"
                else:
                    current_summary = None
                if current and current_summary != self.last_clipboard:
                    self.last_clipboard = current_summary
                    if self.auto_capture:
                        self.add_item(*current)
            except Exception:
                pass
            self.clipboard_after_id = self._safe_after(500, poll)

        self.clipboard_after_id = self._safe_after(500, poll)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._quit_app)
        self.root.bind("<Control-f>", self._focus_search)
        self.root.mainloop()


def acquire_single_instance():
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return None
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        ctypes.windll.user32.MessageBoxW(
            None, "DynaClip is already running.", "DynaClip", 0x40
        )
        kernel32.CloseHandle(handle)
        return None
    return handle


def main():
    mutex_handle = acquire_single_instance()
    if not mutex_handle:
        return
    app = None
    try:
        app = DynaClip(mutex_handle=mutex_handle)
        app.run()
    except Exception:
        if mutex_handle:
            ctypes.windll.kernel32.CloseHandle(mutex_handle)
        raise


if __name__ == "__main__":
    main()
