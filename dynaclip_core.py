import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
from logging.handlers import RotatingFileHandler
from pathlib import Path
import logging
import os
import re
import sys
import time


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
CRYPTPROTECT_UI_FORBIDDEN = 0x0001
SETTINGS_FILE_NAME = "settings.dat"
LOG_FILE_NAME = "dynaclip.log.enc"
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
        handler = EncryptedRotatingFileHandler(log_dir / LOG_FILE_NAME)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger._dynaclip_log_dir = log_dir
    except Exception:
        logger.addHandler(logging.NullHandler())
    return logger, log_dir


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _make_blob(data: bytes) -> DATA_BLOB:
    if not data:
        return DATA_BLOB(0, None)
    buffer = (ctypes.c_byte * len(data)).from_buffer_copy(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))


def dpapi_protect(data: bytes, description: str = "DynaClip") -> bytes:
    if not data:
        return b""
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob = _make_blob(data)
    out_blob = DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        description,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def dpapi_unprotect(data: bytes) -> bytes:
    if not data:
        return b""
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob = _make_blob(data)
    out_blob = DATA_BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def scrub_sensitive_text(value: str) -> str:
    compact = value.strip()
    secret_patterns = [
        r"(?i)api[_-]?key\s*[:=]\s*\S+",
        r"(?i)password\s*[:=]\s*\S+",
        r"(?i)secret\s*[:=]\s*\S+",
        r"(?i)bearer\s+[a-z0-9._\-]+",
        r"(?i)ghp_[a-z0-9]+",
        r"(?i)sk-[a-z0-9]+",
    ]
    for pattern in secret_patterns:
        if re.search(pattern, compact):
            return "[redacted sensitive text]"
    return compact


class EncryptedRotatingFileHandler(logging.Handler):
    def __init__(self, file_path: Path, max_entries: int = 400):
        super().__init__()
        self.file_path = file_path
        self.max_entries = max_entries

    def emit(self, record):
        try:
            message = self.format(record)
            entries = []
            if self.file_path.exists():
                try:
                    encrypted = self.file_path.read_bytes()
                    decrypted = dpapi_unprotect(encrypted).decode("utf-8")
                    entries = json.loads(decrypted)
                except Exception:
                    entries = []
            entries.append(message)
            entries = entries[-self.max_entries :]
            protected = dpapi_protect(json.dumps(entries, ensure_ascii=True).encode("utf-8"))
            self.file_path.write_bytes(protected)
        except Exception:
            pass


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


ULONG_PTR = ctypes.c_size_t


def configure_win32_clipboard_api():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    shell32 = ctypes.windll.shell32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL

    shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    shell32.DragQueryFileW.restype = wintypes.UINT

    return user32, kernel32, shell32


def open_clipboard_with_retry(user32, owner=None, attempts: int = 8, delay_seconds: float = 0.02) -> bool:
    for _ in range(max(1, int(attempts))):
        if user32.OpenClipboard(owner):
            return True
        time.sleep(delay_seconds)
    return False


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
        single_line = self.text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()
        prefix = f"[{self.kind_label}] " if self.kind != "text" else ""
        display = single_line[:44] + "..." if len(single_line) > 44 else single_line
        return prefix + display

    @property
    def formatted_timestamp(self) -> str:
        return self.timestamp.strftime("%H:%M")


def acquire_single_instance():
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return None
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        ctypes.windll.user32.MessageBoxW(None, "DynaClip is already running.", "DynaClip", 0x40)
        kernel32.CloseHandle(handle)
        return None
    return handle
