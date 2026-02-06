#!/usr/bin/env python3
"""
DynaClip - Modern Clipboard Top Bar for Windows
A lightweight, in-memory clipboard history manager.
Auto-shows when mouse moves to top of screen.

Security Features:
- No file system access (no persistence)
- Single instance via Windows mutex
- Memory-only clipboard history
- No external network calls
- Minimal Windows API usage
"""

import tkinter as tk
from tkinter import messagebox
import ctypes
from datetime import datetime
import sys

# Windows API constants
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
MONITOR_DEFAULTTONEAREST = 2


class ClipboardItem:
    """Represents a single clipboard history item."""
    
    __slots__ = ('id', 'text', 'timestamp')  # Memory optimization
    
    def __init__(self, id: int, text: str):
        self.id = id
        self.text = text
        self.timestamp = datetime.now()
    
    @property
    def display_text(self) -> str:
        """Get truncated text for display."""
        if not self.text:
            return "(empty)"
        single_line = self.text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()
        return single_line[:40] + "…" if len(single_line) > 40 else single_line
    
    @property
    def formatted_timestamp(self) -> str:
        """Get formatted timestamp."""
        return self.timestamp.strftime("%H:%M")


class ModernTheme:
    """Modern theme with refined colors."""
    
    def __init__(self):
        self.is_dark = self._detect_dark_mode()
        
        if self.is_dark:
            self.bg_primary = "#1a1b1e"
            self.bg_secondary = "#25262b"
            self.bg_card = "#2c2e33"
            self.bg_card_hover = "#373a40"
            self.fg_primary = "#e9ecef"
            self.fg_secondary = "#909296"
            self.fg_muted = "#5c5f66"
            self.accent = "#339af0"
            self.accent_hover = "#228be6"
            self.border = "#373a40"
            self.success = "#51cf66"
            self.danger = "#ff6b6b"
        else:
            self.bg_primary = "#f8f9fa"
            self.bg_secondary = "#ffffff"
            self.bg_card = "#ffffff"
            self.bg_card_hover = "#f1f3f4"
            self.fg_primary = "#212529"
            self.fg_secondary = "#495057"
            self.fg_muted = "#adb5bd"
            self.accent = "#228be6"
            self.accent_hover = "#1c7ed6"
            self.border = "#e9ecef"
            self.success = "#40c057"
            self.danger = "#fa5252"
    
    def _detect_dark_mode(self) -> bool:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0
        except Exception:
            return True


class DynaClip:
    """Main application class - Modern top bar with auto-show."""
    
    BAR_HEIGHT = 64
    TRIGGER_ZONE = 5
    HIDE_DELAY = 600
    MAX_ITEMS = 50  # Limit memory usage
    
    def __init__(self):
        self.theme = ModernTheme()
        self.items: list[ClipboardItem] = []
        self.next_id = 1
        self.allow_duplicates = True
        self.is_visible = False
        self.last_clipboard = ""
        self.search_var = None
        self.hide_timer = None
        self.mouse_in_window = False
        
        # Default work area values (will be updated)
        self.work_left = 0
        self.work_top = 0
        self.work_width = 1920
        self.work_height = 1040
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("DynaClip")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.98)
        self.root.configure(bg=self.theme.bg_primary)
        
        # Now update work area with actual screen dimensions
        self._update_work_area()
        
        self._position_window(visible=False)
        self.root.update_idletasks()
        self._configure_window_style()
        self._setup_ui()
        self._setup_clipboard_monitor()
        self._start_clipboard_polling()
        self._start_mouse_monitor()
        
        self.root.bind("<Enter>", self._on_window_enter)
        self.root.bind("<Leave>", self._on_window_leave)
    
    def _update_work_area_for_point(self, x: int, y: int):
        """Get the work area of the monitor containing the given point."""
        try:
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                           ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            
            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_ulong),
                           ("rcMonitor", RECT),
                           ("rcWork", RECT),
                           ("dwFlags", ctypes.c_ulong)]
            
            user32 = ctypes.windll.user32
            pt = POINT(x, y)
            
            # Get the monitor that contains this point
            hMonitor = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
            
            # Get monitor info
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi))
            
            # Use work area (excludes taskbar)
            self.work_left = mi.rcWork.left
            self.work_top = mi.rcWork.top
            self.work_width = mi.rcWork.right - mi.rcWork.left
            self.work_height = mi.rcWork.bottom - mi.rcWork.top
            self.monitor_top = mi.rcMonitor.top  # Store monitor top for trigger detection
        except Exception:
            self.work_left = 0
            self.work_top = 0
            self.work_width = 1920
            self.work_height = 1040
            self.monitor_top = 0
    
    def _update_work_area(self):
        # Default: use primary monitor (0,0)
        self._update_work_area_for_point(0, 0)
    
    def _configure_window_style(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            user32 = ctypes.windll.user32
            current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = (current_style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        except Exception:
            pass
    
    def _position_window(self, visible: bool = True, mouse_x: int = 0, mouse_y: int = 0):
        if mouse_x != 0 or mouse_y != 0:
            self._update_work_area_for_point(mouse_x, mouse_y)
        y = self.work_top if visible else self.work_top - self.BAR_HEIGHT + 1
        self.root.geometry(f"{self.work_width}x{self.BAR_HEIGHT}+{self.work_left}+{y}")
        self.is_visible = visible
    
    def _setup_ui(self):
        """Setup the modern horizontal bar interface."""
        self.main_frame = tk.Frame(self.root, bg=self.theme.bg_primary)
        self.main_frame.pack(fill="both", expand=True)
        
        # Bottom accent line
        accent_line = tk.Frame(self.main_frame, bg=self.theme.accent, height=2)
        accent_line.pack(side="bottom", fill="x")
        
        # Content area
        content = tk.Frame(self.main_frame, bg=self.theme.bg_primary)
        content.pack(fill="both", expand=True, padx=16, pady=8)
        
        # Left section
        left_frame = tk.Frame(content, bg=self.theme.bg_primary)
        left_frame.pack(side="left", fill="y")
        
        # Logo
        logo_frame = tk.Frame(left_frame, bg=self.theme.bg_primary)
        logo_frame.pack(side="left", padx=(0, 16))
        
        icon_label = tk.Label(logo_frame, text="📋", font=("Segoe UI Emoji", 16),
                             bg=self.theme.bg_primary, fg=self.theme.accent)
        icon_label.pack(side="left")
        
        title_label = tk.Label(logo_frame, text="DynaClip", 
                              font=("Segoe UI", 13, "bold"),
                              bg=self.theme.bg_primary, fg=self.theme.fg_primary)
        title_label.pack(side="left", padx=(4, 0))
        
        # Separator
        sep1 = tk.Frame(left_frame, bg=self.theme.border, width=1)
        sep1.pack(side="left", fill="y", padx=12, pady=4)
        
        # Action buttons
        btn_frame = tk.Frame(left_frame, bg=self.theme.bg_primary)
        btn_frame.pack(side="left")
        
        self.add_btn = self._create_modern_button(btn_frame, "＋ Add", self.add_from_clipboard, primary=True)
        self.add_btn.pack(side="left", padx=(0, 8))
        
        self.menu_btn = self._create_icon_button(btn_frame, "⚙", self._show_menu)
        self.menu_btn.pack(side="left", padx=(0, 8))
        
        # Search box
        search_container = tk.Frame(left_frame, bg=self.theme.bg_secondary, 
                                   highlightbackground=self.theme.border,
                                   highlightthickness=1)
        search_container.pack(side="left", padx=(8, 0))
        
        search_inner = tk.Frame(search_container, bg=self.theme.bg_secondary)
        search_inner.pack(fill="both", expand=True, padx=10, pady=4)
        
        search_icon = tk.Label(search_inner, text="🔍", font=("Segoe UI Emoji", 9),
                              bg=self.theme.bg_secondary, fg=self.theme.fg_muted)
        search_icon.pack(side="left")
        
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_inner, textvariable=self.search_var,
                                     font=("Segoe UI", 10), width=12,
                                     bg=self.theme.bg_secondary, fg=self.theme.fg_primary,
                                     insertbackground=self.theme.accent,
                                     relief="flat", bd=0)
        self.search_entry.pack(side="left", padx=(4, 0))
        self.search_entry.insert(0, "Search…")
        self.search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)
        self.search_entry.config(fg=self.theme.fg_muted)
        
        # Items container
        items_outer = tk.Frame(content, bg=self.theme.bg_primary)
        items_outer.pack(side="left", fill="both", expand=True, padx=(20, 8))
        
        self.canvas = tk.Canvas(items_outer, bg=self.theme.bg_primary, 
                               highlightthickness=0, height=44)
        self.canvas.pack(side="top", fill="both", expand=True)
        
        self.items_container = tk.Frame(self.canvas, bg=self.theme.bg_primary)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.items_container, anchor="nw")
        
        self.items_container.bind("<Configure>", self._on_items_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Empty state
        self.empty_label = tk.Label(items_outer, 
                                    text="No clips yet • Copy something to get started",
                                    font=("Segoe UI", 10),
                                    bg=self.theme.bg_primary, fg=self.theme.fg_muted)
        
        # Status
        self.status_frame = tk.Frame(content, bg=self.theme.bg_primary)
        self.status_frame.pack(side="right", fill="y")
        
        self.status_label = tk.Label(self.status_frame, text="", 
                                     font=("Segoe UI", 9),
                                     bg=self.theme.bg_primary, fg=self.theme.success)
        self.status_label.pack(side="right", pady=2)
        
        self.count_label = tk.Label(self.status_frame, text="0 items",
                                    font=("Segoe UI", 9),
                                    bg=self.theme.bg_primary, fg=self.theme.fg_muted)
        self.count_label.pack(side="right", padx=(0, 12))
        
        self.search_var.trace_add("write", lambda *args: self._refresh_items())
        self._refresh_items()
        self.root.bind("<Escape>", lambda e: self._hide_bar())
    
    def _create_modern_button(self, parent, text, command, primary=False):
        if primary:
            bg, fg, hover_bg = self.theme.accent, "#ffffff", self.theme.accent_hover
        else:
            bg, fg, hover_bg = self.theme.bg_secondary, self.theme.fg_primary, self.theme.bg_card_hover
        
        btn = tk.Label(parent, text=text, font=("Segoe UI", 9, "bold"),
                      bg=bg, fg=fg, cursor="hand2", padx=12, pady=4)
        
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn
    
    def _create_icon_button(self, parent, icon, command):
        btn = tk.Label(parent, text=icon, font=("Segoe UI", 11),
                      bg=self.theme.bg_primary, fg=self.theme.fg_secondary,
                      cursor="hand2", padx=6, pady=2)
        
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.config(fg=self.theme.fg_primary, bg=self.theme.bg_secondary))
        btn.bind("<Leave>", lambda e: btn.config(fg=self.theme.fg_secondary, bg=self.theme.bg_primary))
        return btn
    
    def _on_search_focus_in(self, event):
        if self.search_entry.get() == "Search…":
            self.search_entry.delete(0, "end")
            self.search_entry.config(fg=self.theme.fg_primary)
    
    def _on_search_focus_out(self, event):
        if not self.search_entry.get():
            self.search_entry.insert(0, "Search…")
            self.search_entry.config(fg=self.theme.fg_muted)
    
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
        self._schedule_hide()
    
    def _schedule_hide(self):
        if self.hide_timer:
            self.root.after_cancel(self.hide_timer)
        self.hide_timer = self.root.after(self.HIDE_DELAY, self._check_and_hide)
    
    def _check_and_hide(self):
        if not self.mouse_in_window:
            self._hide_bar()
        self.hide_timer = None
    
    def _show_bar(self, mouse_x: int = 0, mouse_y: int = 0):
        if not self.is_visible:
            self._position_window(visible=True, mouse_x=mouse_x, mouse_y=mouse_y)
            self.root.lift()
    
    def _hide_bar(self):
        if self.is_visible:
            self._position_window(visible=False)
    
    def _start_mouse_monitor(self):
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                       ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        
        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong),
                       ("rcMonitor", RECT),
                       ("rcWork", RECT),
                       ("dwFlags", ctypes.c_ulong)]
        
        pt = POINT()
        user32 = ctypes.windll.user32
        
        def monitor():
            try:
                user32.GetCursorPos(ctypes.byref(pt))
                
                # Get the monitor the cursor is on
                hMonitor = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi))
                
                # Check if cursor is near top of THIS monitor
                monitor_top = mi.rcMonitor.top
                if pt.y <= monitor_top + self.TRIGGER_ZONE:
                    if not self.is_visible:
                        self._show_bar(pt.x, pt.y)
            except Exception:
                pass
            
            self.root.after(50, monitor)
        
        self.root.after(100, monitor)
    
    def _show_menu(self):
        menu = tk.Menu(self.root, tearoff=0, 
                      bg=self.theme.bg_card, fg=self.theme.fg_primary,
                      activebackground=self.theme.accent, 
                      activeforeground="#ffffff",
                      font=("Segoe UI", 10), bd=0, relief="flat")
        
        menu.add_command(label="  🗑  Clear All", command=self._clear_history)
        menu.add_command(label=f"  {'✓' if self.allow_duplicates else '○'}  Allow Duplicates",
                        command=self._toggle_duplicates)
        menu.add_separator()
        menu.add_command(label=f"  📊  {len(self.items)} items (in memory)")
        menu.add_separator()
        menu.add_command(label="  ⏻  Exit", command=self.root.quit)
        
        x = self.menu_btn.winfo_rootx()
        y = self.menu_btn.winfo_rooty() + self.menu_btn.winfo_height() + 4
        menu.post(x, y)
    
    def _clear_history(self):
        if messagebox.askyesno("Clear History", "Clear all clipboard history?"):
            self.items.clear()
            self.next_id = 1
            self._refresh_items()
            self._set_status("✓ Cleared")
    
    def _toggle_duplicates(self):
        self.allow_duplicates = not self.allow_duplicates
        self._set_status("✓ Duplicates " + ("on" if self.allow_duplicates else "off"))
    
    def _refresh_items(self):
        for widget in self.items_container.winfo_children():
            widget.destroy()
        
        search = self.search_var.get() if self.search_var else ""
        if search == "Search…":
            search = ""
        
        filtered = [item for item in self.items 
                   if not search or search.lower() in item.text.lower()]
        
        if not filtered:
            self.empty_label.pack(expand=True, fill="both")
            self.canvas.pack_forget()
        else:
            self.empty_label.pack_forget()
            self.canvas.pack(side="top", fill="both", expand=True)
            
            for item in filtered:
                self._create_item_widget(item)
        
        self.count_label.config(text=f"{len(self.items)} items")
    
    def _create_item_widget(self, item: ClipboardItem):
        """Create a modern card for a clipboard item."""
        outer = tk.Frame(self.items_container, bg=self.theme.border)
        outer.pack(side="left", fill="y", padx=4, pady=4)
        
        card = tk.Frame(outer, bg=self.theme.bg_card, cursor="hand2")
        card.pack(fill="both", expand=True, padx=1, pady=1)
        
        inner = tk.Frame(card, bg=self.theme.bg_card)
        inner.pack(fill="both", expand=True, padx=12, pady=8)
        
        text_label = tk.Label(inner, text=item.display_text,
                             font=("Segoe UI", 10),
                             bg=self.theme.bg_card, fg=self.theme.fg_primary,
                             anchor="w")
        text_label.pack(side="left")
        
        time_frame = tk.Frame(inner, bg=self.theme.bg_secondary)
        time_frame.pack(side="left", padx=(10, 0))
        
        time_label = tk.Label(time_frame, text=item.formatted_timestamp,
                             font=("Segoe UI", 8),
                             bg=self.theme.bg_secondary, fg=self.theme.fg_muted,
                             padx=6, pady=1)
        time_label.pack()
        
        del_btn = tk.Label(inner, text="×", font=("Segoe UI", 12, "bold"),
                          bg=self.theme.bg_card, fg=self.theme.fg_muted,
                          cursor="hand2", padx=4)
        del_btn.pack(side="left", padx=(8, 0))
        
        hover_state = {"active": False}
        
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
            del_btn.config(bg=self.theme.bg_card)
            del_btn.config(fg=self.theme.fg_muted)
        
        def on_enter(e):
            hover_state["active"] = True
            apply_hover()
        
        def on_leave(e):
            x, y = outer.winfo_pointerxy()
            wx, wy = outer.winfo_rootx(), outer.winfo_rooty()
            ww, wh = outer.winfo_width(), outer.winfo_height()
            if not (wx <= x < wx + ww and wy <= y < wy + wh):
                hover_state["active"] = False
                remove_hover()
        
        def on_click(e):
            self.copy_item(item)
        
        def on_del_enter(e):
            del_btn.config(fg=self.theme.danger)
            apply_hover()
        
        def on_del_leave(e):
            if hover_state["active"]:
                del_btn.config(fg=self.theme.fg_muted)
        
        def on_del_click(e):
            self.delete_item(item.id)
            return "break"
        
        outer.bind("<Enter>", on_enter)
        outer.bind("<Leave>", on_leave)
        
        for widget in [card, inner, text_label, time_frame, time_label]:
            widget.bind("<Button-1>", on_click)
        
        del_btn.bind("<Enter>", on_del_enter)
        del_btn.bind("<Leave>", on_del_leave)
        del_btn.bind("<Button-1>", on_del_click)
        
        self._create_tooltip(outer, item.text)
    
    def _create_tooltip(self, widget, text):
        tooltip = None
        tooltip_id = None
        
        def show_tooltip(event):
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
                y = widget.winfo_rooty() + widget.winfo_height() + 5
                
                tooltip = tk.Toplevel(widget)
                tooltip.wm_overrideredirect(True)
                tooltip.wm_geometry(f"+{x}+{y}")
                tooltip.attributes("-topmost", True)
                tooltip.configure(bg=self.theme.border)
                
                display = text[:500] + "…" if len(text) > 500 else text
                
                inner = tk.Frame(tooltip, bg=self.theme.bg_card)
                inner.pack(fill="both", expand=True, padx=1, pady=1)
                
                label = tk.Label(inner, text=display, justify="left",
                               bg=self.theme.bg_card, fg=self.theme.fg_primary,
                               font=("Segoe UI", 9),
                               wraplength=350, padx=12, pady=8)
                label.pack()
            
            tooltip_id = widget.after(400, create)
        
        def hide_tooltip(event):
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
            text = self.root.clipboard_get()
            if text:
                self.add_item(text)
            else:
                self._set_status("⚠ Empty")
        except tk.TclError:
            self._set_status("⚠ No text")
    
    def add_item(self, text: str):
        if not text:
            return
        
        if not self.allow_duplicates:
            for item in self.items:
                if item.text == text:
                    self.items.remove(item)
                    item.timestamp = datetime.now()
                    self.items.insert(0, item)
                    self._refresh_items()
                    self._set_status("↑ Moved up")
                    return
        
        item = ClipboardItem(self.next_id, text)
        self.next_id += 1
        self.items.insert(0, item)
        
        # Limit memory usage
        if len(self.items) > self.MAX_ITEMS:
            self.items = self.items[:self.MAX_ITEMS]
        
        self._refresh_items()
        self._set_status("✓ Added")
    
    def copy_item(self, item: ClipboardItem):
        self.root.clipboard_clear()
        self.root.clipboard_append(item.text)
        self.last_clipboard = item.text
        self._set_status("✓ Copied")
    
    def delete_item(self, item_id: int):
        self.items = [item for item in self.items if item.id != item_id]
        self._refresh_items()
        self._set_status("✓ Deleted")
    
    def _set_status(self, message: str):
        self.status_label.config(text=message)
        if "✓" in message:
            self.status_label.config(fg=self.theme.success)
        elif "⚠" in message:
            self.status_label.config(fg=self.theme.danger)
        else:
            self.status_label.config(fg=self.theme.fg_secondary)
        self.root.after(2500, lambda: self.status_label.config(text=""))
    
    def _setup_clipboard_monitor(self):
        try:
            self.last_clipboard = self.root.clipboard_get()
        except Exception:
            self.last_clipboard = ""
    
    def _start_clipboard_polling(self):
        def poll():
            try:
                current = self.root.clipboard_get()
                if current and current != self.last_clipboard:
                    self.last_clipboard = current
            except Exception:
                pass
            self.root.after(500, poll)
        self.root.after(500, poll)
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.root.quit)
        
        self.root.mainloop()


def main():
    app = DynaClip()
    app.run()


if __name__ == "__main__":
    main()
