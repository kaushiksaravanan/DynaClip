from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from dynaclip_qt import DynaClipQt, ClipboardItem

app = QApplication([])
w = DynaClipQt()
results = []

for timer in [w.pointer_timer, w.mouse_timer, w.clipboard_timer, w.hotkey_timer]:
    try:
        timer.stop()
    except Exception:
        pass


def record(name, *values):
    results.append((name, *values))


def run_sequence():
    try:
        record('startup_visible', w.isVisible(), w.state)

        w._show_compact()
        QTimer.singleShot(350, seq_expand)
    except Exception as exc:
        record('error_run_sequence', type(exc).__name__, str(exc))
        finish()


def seq_expand():
    try:
        record('after_compact', w.state, w.animating_to, w.isVisible())
        w._expand()
        QTimer.singleShot(400, seq_items)
    except Exception as exc:
        record('error_seq_expand', type(exc).__name__, str(exc))
        finish()


def seq_items():
    try:
        record('after_expand', w.state, w.animating_to, w.expanded_container.isVisible())
        w.add_item('text', 'alpha')
        w.add_item('text', 'beta')
        w.add_item('text', 'beta')
        record('count_with_duplicates', len(w.items))

        w.allow_duplicates = False
        w.add_item('text', 'alpha')
        record('dedupe_move_top', [item.text for item in w.items])

        item = w.items[0]
        w.open_detail_window(item)
        record('detail_windows_after_open', len(w.detail_windows))
        w._clear_history = w.__class__._clear_history.__get__(w, w.__class__)
        w.items = [ClipboardItem(1, 'text', 'persist')]
        w.next_id = 2
        w._refresh_items()
        record('empty_state_after_refresh', w.empty_label.isVisible(), w.empty_label.text())

        w.search_edit.setText('nomatch')
        record('search_nomatch', w.empty_label.isVisible(), w.empty_label.text())
        w.search_edit.setText('')

        w._set_status('Added clip')
        record('meta_label_after_status', w.meta_label.text())
        w._clear_status()
        record('meta_label_after_clear', w.meta_label.text())

        w._toggle_auto_capture()
        w._toggle_startup()
        w._toggle_startup()
        w._toggle_sensitive_filter()
        record('toggles', w.auto_capture, w.run_at_startup, w.filter_sensitive)

        w._collapse_to_compact_or_hide()
        QTimer.singleShot(450, seq_hide)
    except Exception as exc:
        record('error_seq_items', type(exc).__name__, str(exc))
        finish()


def seq_hide():
    try:
        record('after_collapse_request', w.state, w.animating_to, w.pending_state)
        w._collapse_to_compact_or_hide()
        QTimer.singleShot(300, seq_tray)
    except Exception as exc:
        record('error_seq_hide', type(exc).__name__, str(exc))
        finish()


def seq_tray():
    try:
        record('after_hide', w.state, w.animating_to, w.isVisible())
        w._open_from_tray()
        QTimer.singleShot(450, seq_quit)
    except Exception as exc:
        record('error_seq_tray', type(exc).__name__, str(exc))
        finish()


def seq_quit():
    try:
        record('after_open_from_tray', w.state, w.animating_to, w.expanded_container.isVisible())
    finally:
        finish()


def finish():
    for row in results:
        print(row)
    try:
        w._quit_app()
    except Exception as exc:
        print(('error_quit', type(exc).__name__, str(exc)))

QTimer.singleShot(0, run_sequence)
app.exec()
