#!/usr/bin/env python3

import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    Property,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from dynaclip_core import (
    APP_VERSION,
    CF_DIB,
    CF_HDROP,
    CF_UNICODETEXT,
    DROPFILES,
    GHND,
    HOTKEY_ID,
    HOTKEY_LABEL,
    HOTKEY_MODIFIERS,
    MONITORINFO,
    MONITOR_DEFAULTTONEAREST,
    POINT,
    RUN_KEY,
    SETTINGS_FILE_NAME,
    VK_SPACE,
    ClipboardItem,
    acquire_single_instance,
    configure_win32_clipboard_api,
    dpapi_protect,
    dpapi_unprotect,
    get_app_data_dir,
    get_resource_path,
    open_clipboard_with_retry,
    scrub_sensitive_text,
    setup_logger,
)


WM_HOTKEY = 0x0312


class IslandSurface(QFrame):
    def __init__(self):
        super().__init__()
        self._corner_radius = 22.0
        self._content_progress = 0.0
        self._item_count = 0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def getCornerRadius(self):
        return self._corner_radius

    def setCornerRadius(self, value):
        self._corner_radius = float(value)
        self.update()

    cornerRadius = Property(float, getCornerRadius, setCornerRadius)

    def getContentProgress(self):
        return self._content_progress

    def setContentProgress(self, value):
        self._content_progress = max(0.0, min(1.0, float(value)))
        self.update()

    contentProgress = Property(float, getContentProgress, setContentProgress)

    def setItemCount(self, count: int):
        self._item_count = max(0, int(count))
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)

        background = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        background.setColorAt(0.0, QColor(41, 43, 48, 246))
        background.setColorAt(0.42, QColor(23, 24, 28, 244))
        background.setColorAt(1.0, QColor(10, 11, 14, 245))
        painter.fillPath(path, background)

        top_band_height = max(int(rect.height() * 0.26), 12)
        top_band = QRect(rect.left() + 2, rect.top() + 2, rect.width() - 4, top_band_height)
        top_band_path = QPainterPath()
        top_band_path.addRoundedRect(
            top_band,
            max(self._corner_radius - 2, 8),
            max(self._corner_radius - 2, 8),
        )
        painter.fillPath(top_band_path, QColor(255, 255, 255, 10))

        painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
        painter.drawPath(path)

        if self._content_progress > 0.01:
            self._draw_expanded_band(painter, rect)

        self._draw_compact_content(painter, rect)

    def _draw_expanded_band(self, painter: QPainter, rect: QRect):
        band_rect = rect.adjusted(18, 10, -18, -10)
        band_radius = max(self._corner_radius - 6, 18)

        painter.save()
        painter.setOpacity(self._content_progress)
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        painter.setBrush(QColor(255, 255, 255, 6))
        painter.drawRoundedRect(band_rect, band_radius, band_radius)
        painter.restore()

    def _draw_compact_content(self, painter: QPainter, rect: QRect):
        opacity = 1.0 - self._content_progress
        if opacity <= 0.01:
            return

        content_rect = rect.adjusted(18, 8, -18, -8)
        content_rect.translate(0, int(-5 * self._content_progress))

        painter.save()
        painter.setOpacity(opacity)

        icon_font = QFont("Segoe UI Symbol", 11, QFont.Weight.DemiBold)
        title_font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        badge_font = QFont("Segoe UI", 8, QFont.Weight.Bold)

        painter.setFont(icon_font)
        icon_metrics = painter.fontMetrics()
        icon_width = icon_metrics.horizontalAdvance("[]")
        icon_rect = QRect(
            content_rect.left(),
            content_rect.top(),
            icon_width,
            content_rect.height(),
        )
        painter.setPen(QColor("#f4f5f7"))
        painter.drawText(
            icon_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "[]",
        )

        painter.setFont(title_font)
        title_metrics = painter.fontMetrics()
        title_width = title_metrics.horizontalAdvance("DynaClip")
        title_rect = QRect(
            icon_rect.right() + 8,
            content_rect.top(),
            title_width,
            content_rect.height(),
        )
        painter.setPen(QColor("#f8fafc"))
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "DynaClip",
        )

        painter.setFont(badge_font)
        badge_text = str(self._item_count)
        badge_metrics = painter.fontMetrics()
        badge_width = badge_metrics.horizontalAdvance(badge_text) + 16
        badge_rect = QRect(
            min(title_rect.right() + 10, content_rect.right() - badge_width),
            content_rect.center().y() - 9,
            badge_width,
            18,
        )
        painter.setPen(QPen(QColor(255, 255, 255, 26), 1))
        painter.setBrush(QColor(255, 255, 255, 14))
        painter.drawRoundedRect(badge_rect, 9, 9)
        painter.setPen(QColor("#f4f5f7"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)
        painter.restore()


class HorizontalScrollArea(QScrollArea):
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - int(delta / 2))
            event.accept()
            return
        super().wheelEvent(event)


class ClipCardWidget(QFrame):
    activated = Signal(object)
    openRequested = Signal(object)
    deleteRequested = Signal(int)

    def __init__(self, item: ClipboardItem):
        super().__init__()
        self.item = item
        self._double_click_active = False
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(lambda: self.activated.emit(self.item))
        self.setObjectName("clipCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(item.text)
        self.setFixedHeight(48)
        self.setFixedWidth(210)
        self.setStyleSheet(
            "QFrame#clipCard {"
            " background: rgba(255,255,255,0.06);"
            " border: 1px solid rgba(255,255,255,0.12);"
            " border-radius: 15px;"
            "}"
            "QFrame#clipCard:hover {"
            " background: rgba(255,255,255,0.1);"
            " border-color: rgba(255,255,255,0.22);"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 10, 7)
        layout.setSpacing(10)

        text_label = QLabel(item.display_text)
        text_label.setStyleSheet("color: #f5f5f7; font: 500 10pt 'Segoe UI';")
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(text_label, 1)

        time_label = QLabel(item.formatted_timestamp)
        time_label.setStyleSheet(
            "color: #d4d4d8; font: 500 8pt 'Segoe UI';"
            "background: rgba(255,255,255,0.06); border-radius: 9px; padding: 2px 6px;"
        )
        layout.addWidget(time_label)

        delete_button = QToolButton()
        delete_button.setText("x")
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.setStyleSheet(
            "QToolButton { color: #9ca3af; border: 0; background: transparent; font: 700 10pt 'Segoe UI'; padding: 0 2px; }"
            "QToolButton:hover { color: #ef4444; }"
        )
        delete_button.clicked.connect(lambda *_: self.deleteRequested.emit(self.item.id))
        layout.addWidget(delete_button)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._double_click_active:
                self._double_click_active = False
            else:
                self._click_timer.start(QApplication.doubleClickInterval())
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._double_click_active = True
            if self._click_timer.isActive():
                self._click_timer.stop()
            self.openRequested.emit(self.item)
        super().mouseDoubleClickEvent(event)


class ClipDetailDialog(QDialog):
    def __init__(self, parent, item: ClipboardItem, copy_callback, delete_callback):
        super().__init__(parent)
        self.item = item
        self.copy_callback = copy_callback
        self.delete_callback = delete_callback
        self.setWindowTitle(f"DynaClip - Clip {item.id}")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.resize(720, 480)
        self.setMinimumSize(520, 320)
        self.setStyleSheet(
            "QDialog { background: #0f1115; }"
            "QLabel#title { color: #f8fafc; font: 700 12pt 'Segoe UI'; }"
            "QLabel#meta { color: #9ca3af; font: 500 9pt 'Segoe UI'; }"
            "QPushButton { background: rgba(255,255,255,0.08); color: #f4f4f5; border: 1px solid rgba(255,255,255,0.12); border-radius: 13px; padding: 8px 14px; font: 600 9pt 'Segoe UI'; }"
            "QPushButton:hover { background: rgba(255,255,255,0.12); }"
            "QPlainTextEdit { background: #13161c; color: #f4f4f5; border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; padding: 10px; font: 10pt 'Consolas'; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(item.display_text)
        title.setObjectName("title")
        meta = QLabel(f"Clip #{item.id}  {item.kind_label}  {item.formatted_timestamp}")
        meta.setObjectName("meta")
        meta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(title, 1)
        header.addWidget(meta)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        copy_button = QPushButton("Copy")
        copy_button.clicked.connect(lambda *_: self.copy_callback(item))
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(lambda *_: self._delete_and_close())
        toolbar.addWidget(copy_button)
        toolbar.addWidget(delete_button)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        if item.kind == "image":
            self.text_edit.setPlainText(
                f"Bitmap image in DIB format\n\nSize: {len(item.payload)} bytes"
            )
        else:
            self.text_edit.setPlainText(item.text)
        root.addWidget(self.text_edit, 1)

    def _delete_and_close(self):
        self.delete_callback(self.item.id)
        self.close()


class DynaClipQt(QWidget):
    TRIGGER_ZONE = 5
    HIDE_DELAY = 900
    EXPANDED_HIDE_DELAY = 650
    MAX_ITEMS = 50
    POINTER_POLL_INTERVAL = 90

    PILL_WIDTH = 176
    PILL_HEIGHT = 44
    PILL_RADIUS = 22
    EXPANDED_WIDTH = 920
    EXPANDED_HEIGHT = 150
    EXPANDED_RADIUS = 28
    TOP_MARGIN = 10
    CONTROL_ROW_HEIGHT = 36
    SEARCH_ROW_HEIGHT = 36
    EXPANDED_ROW_HEIGHT = 48
    SURFACE_MARGIN_X = 18
    SURFACE_MARGIN_Y = 12

    STATE_HIDDEN = "hidden"
    STATE_COMPACT = "compact"
    STATE_EXPANDED = "expanded"

    def __init__(self, mutex_handle=None):
        super().__init__()
        self.mutex_handle = mutex_handle
        self.logger, self.log_dir = setup_logger()
        self.items = []
        self.next_id = 1
        self.allow_duplicates = True
        self.auto_capture = False
        self.run_at_startup = False
        self.filter_sensitive = True
        self.auto_purge_minutes = 30
        self.last_clipboard = ""
        self.detail_windows = {}
        self.hotkey_registered = False
        self.tray_icon = None
        self.animating_to = None
        self.pending_state = None
        self.geometry_group = None
        self.content_group = None
        self.state = self.STATE_HIDDEN
        self._closing = False
        self.mouse_in_window = False

        self.work_left = 0
        self.work_top = 0
        self.work_width = 1920
        self.work_height = 1040
        self.monitor_top = 0

        self.icon_path = get_resource_path("dynaclip.ico")

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._check_and_hide)

        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self._clear_status)

        self.pointer_timer = QTimer(self)
        self.pointer_timer.timeout.connect(self._poll_pointer)

        self.mouse_timer = QTimer(self)
        self.mouse_timer.timeout.connect(self._monitor_top_edge)

        self.clipboard_timer = QTimer(self)
        self.clipboard_timer.timeout.connect(self._poll_clipboard)

        self.hotkey_timer = QTimer(self)
        self.hotkey_timer.timeout.connect(self._poll_hotkey)

        self._build_window()
        self._load_settings()
        self._update_work_area()
        self._build_ui()
        self._set_geometry_for_state(self.STATE_HIDDEN)
        self._setup_clipboard_monitor()
        self._register_hotkey()
        self._create_tray_icon()
        self._apply_startup_setting()
        self._start_monitors()
        self._refresh_items()
        self.logger.info("qt_app_started version=%s", APP_VERSION)

    def _build_window(self):
        self.setWindowTitle("DynaClip")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.surface = IslandSurface()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 165))
        self.surface.setGraphicsEffect(shadow)
        self.surface.mousePressEvent = self._on_surface_click
        root.addWidget(self.surface)

        self.expanded_container = QWidget(self.surface)
        self.expanded_container.hide()
        self.expanded_opacity = QGraphicsOpacityEffect(self.expanded_container)
        self.expanded_opacity.setOpacity(0.0)
        self.expanded_container.setGraphicsEffect(self.expanded_opacity)

        expanded_layout = QVBoxLayout(self.expanded_container)
        expanded_layout.setContentsMargins(0, 0, 0, 0)
        expanded_layout.setSpacing(8)

        controls = QWidget()
        controls.setFixedHeight(self.CONTROL_ROW_HEIGHT)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)

        self.brand_label = QLabel("[]  DynaClip")
        self.brand_label.setStyleSheet("color: #f5f5f7; font: 700 12pt 'Segoe UI';")
        controls_layout.addWidget(self.brand_label)
        controls_layout.addStretch(1)

        self.add_button = QPushButton("+ Add")
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.setMinimumHeight(self.CONTROL_ROW_HEIGHT)
        self.add_button.setMinimumWidth(84)
        self.add_button.setStyleSheet(self._button_style(primary=True))
        self.add_button.clicked.connect(lambda *_: self.add_from_clipboard())
        controls_layout.addWidget(self.add_button)

        self.menu_button = QToolButton()
        self.menu_button.setText("Menu")
        self.menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_button.setMinimumHeight(self.CONTROL_ROW_HEIGHT)
        self.menu_button.setMinimumWidth(72)
        self.menu_button.setStyleSheet(self._button_style(primary=False))
        self.menu_button.clicked.connect(lambda *_: self._show_menu())
        controls_layout.addWidget(self.menu_button)
        expanded_layout.addWidget(controls)

        search_row = QWidget()
        search_row.setFixedHeight(self.SEARCH_ROW_HEIGHT)
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumHeight(self.SEARCH_ROW_HEIGHT)
        self.search_edit.setMinimumWidth(0)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_edit.setStyleSheet(
            "QLineEdit { background: rgba(255,255,255,0.08); color: #f4f4f5; border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 8px 12px; font: 500 10pt 'Segoe UI'; }"
            "QLineEdit:focus { border-color: rgba(255,255,255,0.24); }"
        )
        self.search_edit.textChanged.connect(self._refresh_items)
        search_layout.addWidget(self.search_edit, 1)

        self.meta_label = QLabel("0 items")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.meta_label.setFixedHeight(self.SEARCH_ROW_HEIGHT)
        self.meta_label.setMinimumWidth(96)
        self.meta_label.setMaximumWidth(180)
        self.meta_label.setStyleSheet("color: #a1a1aa; font: 500 9pt 'Segoe UI'; padding-left: 8px;")
        search_layout.addWidget(self.meta_label, 0)
        expanded_layout.addWidget(search_row)

        items_panel = QWidget()
        items_panel.setFixedHeight(self.EXPANDED_ROW_HEIGHT)
        items_panel_layout = QVBoxLayout(items_panel)
        items_panel_layout.setContentsMargins(0, 0, 0, 0)
        items_panel_layout.setSpacing(0)

        self.items_scroll = HorizontalScrollArea()
        self.items_scroll.setFixedHeight(self.EXPANDED_ROW_HEIGHT)
        self.items_scroll.setWidgetResizable(True)
        self.items_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.items_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.items_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.items_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: 0; }"
            "QScrollBar:horizontal { background: transparent; height: 6px; margin: 0; }"
            "QScrollBar::handle:horizontal { background: rgba(255,255,255,0.18); border-radius: 3px; }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
        )

        self.items_host = QWidget()
        self.items_layout = QHBoxLayout(self.items_host)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)
        self.items_scroll.setWidget(self.items_host)

        self.empty_label = QLabel("No clips yet")
        self.empty_label.setFixedHeight(self.EXPANDED_ROW_HEIGHT)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #9ca3af; font: 500 10pt 'Segoe UI';")

        items_panel_layout.addWidget(self.items_scroll)
        items_panel_layout.addWidget(self.empty_label)
        expanded_layout.addWidget(items_panel)

        self._layout_expanded_container()

        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self._focus_search)
        self.escape_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.escape_shortcut.activated.connect(self._collapse_to_compact_or_hide)

    def _button_style(self, primary=False):
        if primary:
            return (
                "QPushButton { background: rgba(255,255,255,0.1); color: #f4f4f5; border: 1px solid rgba(255,255,255,0.14); border-radius: 15px; padding: 8px 14px; font: 600 10pt 'Segoe UI'; }"
                "QPushButton:hover { background: rgba(255,255,255,0.14); }"
            )
        return (
            "QToolButton { background: rgba(255,255,255,0.08); color: #f4f4f5; border: 1px solid rgba(255,255,255,0.12); border-radius: 15px; padding: 7px 12px; font: 700 10pt 'Segoe UI'; }"
            "QToolButton:hover { background: rgba(255,255,255,0.12); }"
        )

    def _layout_expanded_container(self):
        if not hasattr(self, "surface") or not hasattr(self, "expanded_container"):
            return
        width = max(self.surface.width() - (self.SURFACE_MARGIN_X * 2), 0)
        height = max(self.surface.height() - (self.SURFACE_MARGIN_Y * 2), 0)
        self.expanded_container.setGeometry(
            self.SURFACE_MARGIN_X,
            self.SURFACE_MARGIN_Y,
            width,
            height,
        )

    def _outer_horizontal_margin(self) -> int:
        return max(16, min(38, self.work_width // 28))

    def _compact_width_for_work_area(self) -> int:
        max_available = max(self.work_width - (self._outer_horizontal_margin() * 2), 132)
        return max(148, min(self.PILL_WIDTH, max_available))

    def _expanded_width_for_work_area(self) -> int:
        max_available = max(
            self.work_width - (self._outer_horizontal_margin() * 2),
            self._compact_width_for_work_area(),
        )
        preferred = max(560, int(self.work_width * 0.72))
        return max(
            self._compact_width_for_work_area(),
            min(self.EXPANDED_WIDTH, preferred, max_available),
        )

    def _expanded_height_for_work_area(self, width: int) -> int:
        preferred = self.EXPANDED_HEIGHT + (8 if width < 640 else 0)
        max_available = max(self.work_height - self.TOP_MARGIN - 24, self.PILL_HEIGHT)
        return max(self.PILL_HEIGHT, min(preferred, max_available))

    def _refresh_work_area_for_state(self, target_state: str):
        try:
            if self.isVisible() and self.state != self.STATE_HIDDEN:
                point = self.frameGeometry().center()
            elif self.animating_to is not None and self.isVisible():
                point = self.frameGeometry().center()
            else:
                point = QCursor.pos()
            self._update_work_area_for_point(point.x(), point.y())
        except Exception:
            self._update_work_area_for_point(0, 0)

    def _load_settings(self):
        settings_path = get_app_data_dir() / SETTINGS_FILE_NAME
        if not settings_path.exists():
            return
        try:
            decrypted = dpapi_unprotect(settings_path.read_bytes()).decode("utf-8")
            data = json.loads(decrypted)
            self.allow_duplicates = bool(data.get("allow_duplicates", True))
            self.auto_capture = bool(data.get("auto_capture", False))
            self.run_at_startup = bool(data.get("run_at_startup", False))
            self.filter_sensitive = bool(data.get("filter_sensitive", True))
            self.auto_purge_minutes = int(data.get("auto_purge_minutes", 30))
        except Exception as exc:
            self.logger.warning("qt_settings_load_failed error=%s", exc.__class__.__name__)

    def _save_settings(self):
        try:
            settings_path = get_app_data_dir() / SETTINGS_FILE_NAME
            payload = json.dumps(
                {
                    "allow_duplicates": self.allow_duplicates,
                    "auto_capture": self.auto_capture,
                    "run_at_startup": self.run_at_startup,
                    "filter_sensitive": self.filter_sensitive,
                    "auto_purge_minutes": self.auto_purge_minutes,
                },
                ensure_ascii=True,
            ).encode("utf-8")
            settings_path.write_bytes(dpapi_protect(payload))
        except Exception as exc:
            self.logger.warning("qt_settings_save_failed error=%s", exc.__class__.__name__)

    def _apply_startup_setting(self):
        try:
            import winreg

            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY)
            if self.run_at_startup:
                executable = sys.executable
                target = executable
                if executable.lower().endswith("python.exe") or executable.lower().endswith("pythonw.exe"):
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
            self.logger.warning("qt_startup_setting_failed error=%s", exc.__class__.__name__)

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
                "qt_startup_shortcut_failed error=%s", exc.__class__.__name__
            )

    def _remove_startup_shortcut_fallback(self):
        try:
            shortcut = self._startup_shortcut_path()
            if shortcut.exists():
                shortcut.unlink()
        except Exception:
            pass

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
        try:
            point = QCursor.pos()
            self._update_work_area_for_point(point.x(), point.y())
        except Exception:
            self._update_work_area_for_point(0, 0)

    def _centered_x(self, width: int) -> int:
        return self.work_left + max((self.work_width - width) // 2, 0)

    def _target_bounds_for_state(self, state: str):
        self._refresh_work_area_for_state(state)
        if state == self.STATE_EXPANDED:
            width = self._expanded_width_for_work_area()
            height = self._expanded_height_for_work_area(width)
            radius = self.EXPANDED_RADIUS
            x = self._centered_x(width)
            y = self.work_top + self.TOP_MARGIN
        elif state == self.STATE_COMPACT:
            width = self._compact_width_for_work_area()
            height = self.PILL_HEIGHT
            radius = self.PILL_RADIUS
            x = self._centered_x(width)
            y = self.work_top + self.TOP_MARGIN
        else:
            width = self._compact_width_for_work_area()
            height = self.PILL_HEIGHT
            radius = self.PILL_RADIUS
            x = self._centered_x(width)
            y = self.work_top - height + 6
        return QRect(x, y, width, height), radius

    def _set_geometry_for_state(self, state: str):
        rect, radius = self._target_bounds_for_state(state)
        self.setGeometry(rect)
        self.surface.setCornerRadius(radius)
        self.surface.setContentProgress(1.0 if state == self.STATE_EXPANDED else 0.0)
        self.expanded_opacity.setOpacity(1.0 if state == self.STATE_EXPANDED else 0.0)
        self.expanded_container.setVisible(state == self.STATE_EXPANDED)
        self._layout_expanded_container()
        self.state = state
        if state == self.STATE_HIDDEN:
            self.hide()
        else:
            self.show()

    def _apply_state(self, state: str):
        if self.animating_to is not None:
            self.pending_state = state
            return
        rect, radius = self._target_bounds_for_state(state)
        self.animating_to = state
        self._start_geometry_animation(rect, radius)
        self._start_content_animation(1.0 if state == self.STATE_EXPANDED else 0.0)

    def _start_geometry_animation(self, target: QRect, radius: float):
        if self.geometry_group:
            self.geometry_group.stop()

        start = self.geometry()
        sequence = QSequentialAnimationGroup(self)

        if self.animating_to == self.STATE_EXPANDED:
            squeeze_width = max(start.width() - 10, self._compact_width_for_work_area() - 6)
            squeeze_height = max(start.height() - 3, self.PILL_HEIGHT - 2)
            squeeze = QRect(
                start.center().x() - squeeze_width // 2,
                start.center().y() - squeeze_height // 2,
                squeeze_width,
                squeeze_height,
            )
            stretch_width = min(
                target.width() + 12,
                max(self.work_width - (self._outer_horizontal_margin() * 2), target.width()),
            )
            stretch = QRect(
                target.center().x() - stretch_width // 2,
                start.y(),
                stretch_width,
                max(start.height() + 10, 52),
            )

            phase_one = QPropertyAnimation(self, b"geometry")
            phase_one.setDuration(55)
            phase_one.setStartValue(start)
            phase_one.setEndValue(squeeze)
            phase_one.setEasingCurve(QEasingCurve.Type.OutCubic)

            phase_two = QPropertyAnimation(self, b"geometry")
            phase_two.setDuration(145)
            phase_two.setStartValue(squeeze)
            phase_two.setEndValue(stretch)
            phase_two.setEasingCurve(QEasingCurve.Type.OutCubic)

            phase_three = QPropertyAnimation(self, b"geometry")
            phase_three.setDuration(120)
            phase_three.setStartValue(stretch)
            phase_three.setEndValue(target)
            phase_three.setEasingCurve(QEasingCurve.Type.OutQuad)

            sequence.addAnimation(phase_one)
            sequence.addAnimation(phase_two)
            sequence.addAnimation(phase_three)
        else:
            collapse_mid = QRect(
                start.center().x() - (target.width() + 10) // 2,
                start.y() + 4,
                target.width() + 10,
                max(self.PILL_HEIGHT + 2, start.height() - 18),
            )

            phase_one = QPropertyAnimation(self, b"geometry")
            phase_one.setDuration(110)
            phase_one.setStartValue(start)
            phase_one.setEndValue(collapse_mid)
            phase_one.setEasingCurve(QEasingCurve.Type.OutCubic)

            phase_two = QPropertyAnimation(self, b"geometry")
            phase_two.setDuration(95)
            phase_two.setStartValue(collapse_mid)
            phase_two.setEndValue(target)
            phase_two.setEasingCurve(QEasingCurve.Type.OutCubic)

            sequence.addAnimation(phase_one)
            sequence.addAnimation(phase_two)

        radius_animation = QPropertyAnimation(self.surface, b"cornerRadius")
        radius_animation.setDuration(300 if self.animating_to == self.STATE_EXPANDED else 190)
        radius_animation.setStartValue(self.surface.getCornerRadius())
        radius_animation.setEndValue(radius)
        radius_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        parallel = QParallelAnimationGroup(self)
        parallel.addAnimation(sequence)
        parallel.addAnimation(radius_animation)
        parallel.finished.connect(self._on_geometry_finished)
        parallel.start()
        self.geometry_group = parallel

    def _start_content_animation(self, target_progress: float):
        if self.content_group:
            self.content_group.stop()

        current = self.surface.getContentProgress()
        if abs(current - target_progress) < 0.001:
            if target_progress <= 0.0:
                self.expanded_container.hide()
            return

        if target_progress > current:
            self.expanded_container.show()

        compact_animation = QPropertyAnimation(self.surface, b"contentProgress")
        compact_animation.setStartValue(current)
        compact_animation.setEndValue(target_progress)
        compact_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        expanded_animation = QPropertyAnimation(self.expanded_opacity, b"opacity")
        expanded_animation.setStartValue(self.expanded_opacity.opacity())
        expanded_animation.setEndValue(target_progress)
        expanded_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        if target_progress > current:
            compact_animation.setDuration(170)
            expanded_animation.setDuration(170)
        else:
            compact_animation.setDuration(90)
            expanded_animation.setDuration(90)

        parallel = QParallelAnimationGroup(self)
        parallel.addAnimation(compact_animation)
        parallel.addAnimation(expanded_animation)

        sequence = QSequentialAnimationGroup(self)
        if target_progress > current:
            sequence.addPause(150)
        sequence.addAnimation(parallel)
        sequence.finished.connect(self._on_content_animation_finished)
        sequence.start()
        self.content_group = sequence

    def _on_geometry_finished(self):
        if self.animating_to is None:
            return
        self.state = self.animating_to
        if self.state != self.STATE_EXPANDED and self.expanded_opacity.opacity() <= 0.01:
            self.expanded_container.hide()
        if self.state == self.STATE_HIDDEN:
            self.hide()
        else:
            self.show()
        self.animating_to = None
        if self.pending_state is not None:
            next_state = self.pending_state
            self.pending_state = None
            if next_state != self.state:
                self._apply_state(next_state)

    def _on_content_animation_finished(self):
        if self.animating_to != self.STATE_EXPANDED and self.state != self.STATE_EXPANDED:
            self.expanded_container.hide()

    def _start_monitors(self):
        self.pointer_timer.start(self.POINTER_POLL_INTERVAL)
        self.mouse_timer.start(60)
        self.clipboard_timer.start(500)
        if self.hotkey_registered:
            self.hotkey_timer.start(100)

    def _register_hotkey(self):
        try:
            if ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, HOTKEY_MODIFIERS, VK_SPACE):
                self.hotkey_registered = True
        except Exception:
            self.hotkey_registered = False

    def _poll_hotkey(self):
        try:
            msg = wintypes.MSG()
            pm_remove = 0x0001
            while ctypes.windll.user32.PeekMessageW(
                ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, pm_remove
            ):
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self._toggle_visibility()
        except Exception:
            pass

    def _create_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = (
            QIcon(str(self.icon_path))
            if self.icon_path.exists()
            else QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self.tray_icon = QSystemTrayIcon(icon, self)
        menu = QMenu()
        open_action = QAction("Open", menu)
        open_action.triggered.connect(lambda *_: self._open_from_tray())
        menu.addAction(open_action)

        self.tray_auto_action = QAction("Auto Capture", menu, checkable=True)
        self.tray_auto_action.triggered.connect(lambda *_: self._toggle_auto_capture())
        menu.addAction(self.tray_auto_action)

        self.tray_startup_action = QAction("Run at Startup", menu, checkable=True)
        self.tray_startup_action.triggered.connect(lambda *_: self._toggle_startup())
        menu.addAction(self.tray_startup_action)

        menu.addSeparator()
        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(lambda *_: self._quit_app())
        menu.addAction(exit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self._update_tray_actions()
        self.tray_icon.show()

    def _update_tray_actions(self):
        if not self.tray_icon:
            return
        self.tray_auto_action.setChecked(self.auto_capture)
        self.tray_startup_action.setChecked(self.run_at_startup)
        self.tray_icon.setToolTip(f"DynaClip {APP_VERSION}")

    def _open_from_tray(self):
        if self.hide_timer.isActive():
            self.hide_timer.stop()
        self.show()
        self.raise_()
        if self.state == self.STATE_HIDDEN:
            self._set_geometry_for_state(self.STATE_COMPACT)
        if self.animating_to is None and self.state != self.STATE_EXPANDED:
            self._apply_state(self.STATE_EXPANDED)

    def _on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_visibility()

    def _poll_pointer(self):
        try:
            self.mouse_in_window = self._is_pointer_inside_any_window()
        except Exception:
            pass

    def _monitor_top_edge(self):
        try:
            pt = POINT()
            user32 = ctypes.windll.user32
            user32.GetCursorPos(ctypes.byref(pt))
            h_monitor = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(h_monitor, ctypes.byref(mi))
            if pt.y <= mi.rcMonitor.top + self.TRIGGER_ZONE and self.state == self.STATE_HIDDEN:
                self._show_compact(pt.x, pt.y)
        except Exception:
            pass

    def _show_compact(self, mouse_x=0, mouse_y=0):
        if mouse_x or mouse_y:
            self._update_work_area_for_point(mouse_x, mouse_y)
        if self.hide_timer.isActive():
            self.hide_timer.stop()
        self.show()
        self.raise_()
        if self.animating_to is not None:
            self.pending_state = self.STATE_COMPACT
            return
        if self.state == self.STATE_HIDDEN:
            self._apply_state(self.STATE_COMPACT)

    def _expand(self):
        if self.state == self.STATE_EXPANDED and self.animating_to is None:
            return
        if self.hide_timer.isActive():
            self.hide_timer.stop()
        self.show()
        self.raise_()
        if self.animating_to is not None:
            self.pending_state = self.STATE_EXPANDED
            return
        if self.state == self.STATE_HIDDEN:
            self._set_geometry_for_state(self.STATE_COMPACT)
        self._apply_state(self.STATE_EXPANDED)

    def _toggle_visibility(self):
        if self.state == self.STATE_HIDDEN:
            self._show_compact()
        elif self.state == self.STATE_COMPACT:
            self._expand()
        else:
            self._collapse_to_compact_or_hide()

    def _collapse_to_compact_or_hide(self):
        if self.animating_to is not None:
            if self.animating_to == self.STATE_EXPANDED or self.state == self.STATE_EXPANDED:
                self.pending_state = self.STATE_COMPACT
            elif self.animating_to == self.STATE_COMPACT or self.state == self.STATE_COMPACT:
                self.pending_state = self.STATE_HIDDEN
            return
        if self.state == self.STATE_EXPANDED:
            self._apply_state(self.STATE_COMPACT)
            self._schedule_hide(self.HIDE_DELAY)
        elif self.state == self.STATE_COMPACT:
            self._apply_state(self.STATE_HIDDEN)

    def _schedule_hide(self, delay):
        self.hide_timer.start(delay)

    def _check_and_hide(self):
        if QApplication.activePopupWidget() or QApplication.activeModalWidget():
            self._schedule_hide(self.EXPANDED_HIDE_DELAY if self.state == self.STATE_EXPANDED else self.HIDE_DELAY)
            return
        if not self._is_pointer_inside_any_window():
            self._collapse_to_compact_or_hide()

    def _is_pointer_inside_window(self, window):
        try:
            if not window or not window.isVisible():
                return False
            return window.frameGeometry().contains(QCursor.pos())
        except Exception:
            return False

    def _is_pointer_inside_any_window(self):
        if self._is_pointer_inside_window(self):
            return True
        for window in list(self.detail_windows.values()):
            if self._is_pointer_inside_window(window):
                return True
        return False

    def enterEvent(self, event):
        if self.hide_timer.isActive():
            self.hide_timer.stop()
        super().enterEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_expanded_container()

    def leaveEvent(self, event):
        delay = self.EXPANDED_HIDE_DELAY if self.state == self.STATE_EXPANDED else self.HIDE_DELAY
        self._schedule_hide(delay)
        super().leaveEvent(event)

    def _show_menu(self):
        self._refresh_work_area_for_state(self.state)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #17191e; color: #f4f4f5; border: 1px solid rgba(255,255,255,0.08); padding: 4px; font: 500 9pt 'Segoe UI'; }"
            "QMenu::item { padding: 7px 14px; border-radius: 8px; }"
            "QMenu::item:selected { background: rgba(255,255,255,0.08); }"
        )

        clear_action = menu.addAction("Clear All")
        clear_action.triggered.connect(lambda *_: self._clear_history())

        duplicate_action = QAction("Allow Duplicates", menu, checkable=True)
        duplicate_action.setChecked(self.allow_duplicates)
        duplicate_action.triggered.connect(lambda *_: self._toggle_duplicates())
        menu.addAction(duplicate_action)

        auto_action = QAction("Auto Capture", menu, checkable=True)
        auto_action.setChecked(self.auto_capture)
        auto_action.triggered.connect(lambda *_: self._toggle_auto_capture())
        menu.addAction(auto_action)

        sensitive_action = QAction("Filter Sensitive", menu, checkable=True)
        sensitive_action.setChecked(self.filter_sensitive)
        sensitive_action.triggered.connect(lambda *_: self._toggle_sensitive_filter())
        menu.addAction(sensitive_action)

        startup_action = QAction("Run at Startup", menu, checkable=True)
        startup_action.setChecked(self.run_at_startup)
        startup_action.triggered.connect(lambda *_: self._toggle_startup())
        menu.addAction(startup_action)

        menu.addSeparator()
        info_action = QAction(f"{len(self.items)} items in memory", menu)
        info_action.setEnabled(False)
        menu.addAction(info_action)
        purge_action = QAction(f"Auto purge after {self.auto_purge_minutes}m", menu)
        purge_action.setEnabled(False)
        menu.addAction(purge_action)
        hotkey_action = QAction(f"{HOTKEY_LABEL} toggle hotkey", menu)
        hotkey_action.setEnabled(False)
        menu.addAction(hotkey_action)
        menu.addSeparator()
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(lambda *_: self._quit_app())

        pos = self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft())
        menu_size = menu.sizeHint()
        screen = QGuiApplication.screenAt(pos) or self.screen() or QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            x = min(max(pos.x(), available.left() + 8), available.right() - menu_size.width() - 8)
            y = pos.y() + 6
            if y + menu_size.height() > available.bottom() - 8:
                top_pos = self.menu_button.mapToGlobal(self.menu_button.rect().topLeft())
                y = max(available.top() + 8, top_pos.y() - menu_size.height() - 6)
            pos = QPoint(x, y)
        else:
            pos = pos + QPoint(0, 6)
        if self.hide_timer.isActive():
            self.hide_timer.stop()
        menu.exec(pos)
        if not self._is_pointer_inside_any_window():
            self._schedule_hide(self.EXPANDED_HIDE_DELAY if self.state == self.STATE_EXPANDED else self.HIDE_DELAY)

    def _clear_history(self):
        answer = QMessageBox.question(
            self,
            "Clear History",
            "Clear all clipboard history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            for window in list(self.detail_windows.values()):
                try:
                    window.close()
                except Exception:
                    pass
            self.detail_windows.clear()
            self.items.clear()
            self.next_id = 1
            self._refresh_items()
            self._set_status("History cleared")

    def _toggle_duplicates(self):
        self.allow_duplicates = not self.allow_duplicates
        if not self.allow_duplicates:
            deduped = []
            seen = set()
            for item in self.items:
                if item.fingerprint in seen:
                    continue
                seen.add(item.fingerprint)
                deduped.append(item)
            if len(deduped) != len(self.items):
                self.items = deduped
                self._refresh_items()
        self._save_settings()
        self._set_status("Duplicates on" if self.allow_duplicates else "Duplicates off")

    def _toggle_auto_capture(self):
        self.auto_capture = not self.auto_capture
        self._save_settings()
        self._update_tray_actions()
        self._set_status("Auto capture on" if self.auto_capture else "Auto capture off")

    def _toggle_startup(self):
        self.run_at_startup = not self.run_at_startup
        self._save_settings()
        self._apply_startup_setting()
        self._update_tray_actions()
        self._set_status("Startup on" if self.run_at_startup else "Startup off")

    def _toggle_sensitive_filter(self):
        self.filter_sensitive = not self.filter_sensitive
        self._save_settings()
        self._set_status(
            "Sensitive filter on" if self.filter_sensitive else "Sensitive filter off"
        )

    def _purge_expired_items(self):
        if self.auto_purge_minutes <= 0:
            return False
        cutoff = datetime.now() - timedelta(minutes=self.auto_purge_minutes)
        original_count = len(self.items)
        self.items = [item for item in self.items if item.timestamp >= cutoff]
        if len(self.items) != original_count:
            self.logger.info("qt_items_purged count=%s", original_count - len(self.items))
            return True
        return False

    def _is_sensitive_item(self, kind: str, payload) -> bool:
        if kind != "text" or not self.filter_sensitive:
            return False
        text = payload.strip()
        if len(text) > 2000:
            return True
        return scrub_sensitive_text(text) != text

    def _read_clipboard_item(self):
        user32, kernel32, shell32 = configure_win32_clipboard_api()

        if not open_clipboard_with_retry(user32):
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
        user32, kernel32, _ = configure_win32_clipboard_api()
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
            ctypes.memmove(pointer + ctypes.sizeof(DROPFILES), payload_bytes, len(payload_bytes))
        finally:
            kernel32.GlobalUnlock(h_global)

        if not open_clipboard_with_retry(user32):
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
        user32, kernel32, _ = configure_win32_clipboard_api()
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

        if not open_clipboard_with_retry(user32):
            kernel32.GlobalFree(h_global)
            raise RuntimeError("OpenClipboard failed")
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(CF_DIB, h_global):
                kernel32.GlobalFree(h_global)
                raise RuntimeError("SetClipboardData failed")
        finally:
            user32.CloseClipboard()

    def _clipboard_summary(self, kind: str, payload):
        return ClipboardItem(-1, kind, payload).fingerprint

    def _setup_clipboard_monitor(self):
        try:
            current = self._read_clipboard_item()
            if current:
                self.last_clipboard = self._clipboard_summary(current[0], current[1])
            else:
                self.last_clipboard = ""
        except Exception:
            self.last_clipboard = ""

    def _poll_clipboard(self):
        try:
            current = self._read_clipboard_item()
            summary = self._clipboard_summary(current[0], current[1]) if current else None
            if current and summary != self.last_clipboard:
                self.last_clipboard = summary
                if self.auto_capture:
                    self.add_item(*current)
        except Exception:
            pass

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
        if self._is_sensitive_item(kind, payload):
            self._set_status("Sensitive clip skipped")
            self.logger.info("qt_sensitive_item_skipped kind=%s", kind)
            return

        incoming_fingerprint = ClipboardItem(-1, kind, payload).fingerprint

        if not self.allow_duplicates:
            for item in list(self.items):
                if item.fingerprint == incoming_fingerprint:
                    self.items.remove(item)
                    item.timestamp = datetime.now()
                    self.items.insert(0, item)
                    self._refresh_items()
                    self._set_status("Moved item to top")
                    self.logger.info("qt_item_bumped_to_top")
                    return

        item = ClipboardItem(self.next_id, kind, payload)
        self.next_id += 1
        self.items.insert(0, item)
        if len(self.items) > self.MAX_ITEMS:
            self.items = self.items[: self.MAX_ITEMS]
        self._refresh_items()
        self._set_status("Added clip")
        self.logger.info("qt_item_added count=%s", len(self.items))

    def copy_item(self, item: ClipboardItem):
        try:
            if item.kind == "text":
                QGuiApplication.clipboard().setText(item.payload)
            elif item.kind == "files":
                self._copy_files_to_clipboard(item.payload)
            elif item.kind == "image":
                self._copy_image_to_clipboard(item.payload)
            self.last_clipboard = item.fingerprint
            self._set_status("Copied")
            self.logger.info("qt_item_copied item_id=%s kind=%s", item.id, item.kind)
        except Exception as exc:
            self._set_status("Copy failed")
            self.logger.warning(
                "qt_item_copy_failed item_id=%s error=%s",
                item.id,
                exc.__class__.__name__,
            )

    def delete_item(self, item_id: int):
        detail = self.detail_windows.pop(item_id, None)
        if detail:
            try:
                detail.close()
            except Exception:
                pass
        self.items = [item for item in self.items if item.id != item_id]
        self._refresh_items()
        self._set_status("Deleted")
        self.logger.info("qt_item_deleted item_id=%s count=%s", item_id, len(self.items))

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_items(self):
        self._purge_expired_items()
        self._clear_layout(self.items_layout)
        search = self.search_edit.text().strip().lower() if hasattr(self, "search_edit") else ""
        filtered = [
            item
            for item in self.items
            if not search
            or search in item.text.lower()
            or search in item.kind_label.lower()
        ]

        for item in filtered:
            card = ClipCardWidget(item)
            card.activated.connect(self.copy_item)
            card.openRequested.connect(self.open_detail_window)
            card.deleteRequested.connect(self.delete_item)
            self.items_layout.addWidget(card)
        self.items_layout.addStretch(1)

        has_items = bool(filtered)
        self.items_scroll.setVisible(has_items)
        self.empty_label.setVisible(not has_items)
        if not has_items:
            self.empty_label.setText("No matches" if search else "No clips yet")
        self.surface.setItemCount(len(self.items))
        self._update_meta_label()

    def open_detail_window(self, item: ClipboardItem):
        existing = self.detail_windows.get(item.id)
        if existing and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

        dialog = ClipDetailDialog(self, item, self.copy_item, self.delete_item)
        dialog.destroyed.connect(lambda *_: self.detail_windows.pop(item.id, None))
        self.detail_windows[item.id] = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _set_status(self, message: str):
        self._status_message = message
        if "Copied" in message or "Added" in message or "Moved" in message:
            color = "#d4d4d8"
        elif "Deleted" in message:
            color = "#fca5a5"
        elif "failed" in message.lower() or "Unsupported" in message:
            color = "#fca5a5"
        else:
            color = "#e4e4e7"
        self._status_color = color
        self._update_meta_label()
        self.status_timer.start(2200)

    def _clear_status(self):
        self._status_message = ""
        self._status_color = None
        self._update_meta_label()

    def _update_meta_label(self):
        count_text = f"{len(self.items)} items"
        message = getattr(self, "_status_message", "")
        if message:
            self.meta_label.setText(f"{count_text}  {message}")
            color = getattr(self, "_status_color", "#a1a1aa")
            self.meta_label.setStyleSheet(
                f"color: {color}; font: 600 9pt 'Segoe UI'; padding-left: 8px;"
            )
        else:
            self.meta_label.setText(count_text)
            self.meta_label.setStyleSheet(
                "color: #a1a1aa; font: 500 9pt 'Segoe UI'; padding-left: 8px;"
            )
        self.meta_label.setToolTip(self.meta_label.text())

    def _focus_search(self):
        if self.state != self.STATE_EXPANDED:
            return
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _on_surface_click(self, _event):
        if self.state != self.STATE_EXPANDED:
            self._expand()

    def closeEvent(self, event):
        if self._closing:
            event.accept()
            return
        event.ignore()
        self._quit_app()

    def _quit_app(self):
        if self._closing:
            return
        self._closing = True

        for timer in [
            self.hide_timer,
            self.status_timer,
            self.pointer_timer,
            self.mouse_timer,
            self.clipboard_timer,
            self.hotkey_timer,
        ]:
            try:
                timer.stop()
            except Exception:
                pass

        if self.hotkey_registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            except Exception:
                pass
            self.hotkey_registered = False

        for window in list(self.detail_windows.values()):
            try:
                window.close()
            except Exception:
                pass
        self.detail_windows.clear()

        if self.tray_icon:
            try:
                self.tray_icon.hide()
            except Exception:
                pass
            self.tray_icon = None

        if self.mutex_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
            except Exception:
                pass
            self.mutex_handle = None

        self.hide()
        self.close()
        QApplication.instance().quit()


def main():
    mutex_handle = acquire_single_instance()
    if not mutex_handle:
        return
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = None
    try:
        window = DynaClipQt(mutex_handle=mutex_handle)
        sys.exit(app.exec())
    except Exception:
        if window and window.mutex_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(window.mutex_handle)
            except Exception:
                pass
        elif mutex_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(mutex_handle)
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()
