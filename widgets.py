"""Custom Qt widgets for ComicVault."""
import os
import re
import textwrap
import zipfile
import xml.etree.ElementTree as ET

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QMimeData, pyqtSignal
from PyQt6.QtGui import QIcon

from config import APP_ICON_PATH, log
from utils import parse_comic_filename, natural_sort_key

try:
    import rarfile
    HAS_RAR = True
except ImportError:
    HAS_RAR = False


def _mime_local_comic_paths(mime: QMimeData) -> list:
    """Resolve .cbz/.cbr paths from Explorer / other apps (urls + text/uri-list fallback)."""
    out = []
    seen = set()
    if mime.hasUrls():
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            p = os.path.normpath(url.toLocalFile())
            low = p.lower()
            if low.endswith((".cbz", ".cbr")) and os.path.isfile(p) and p not in seen:
                seen.add(p)
                out.append(p)
    if out:
        return out
    if mime.hasFormat("text/uri-list"):
        try:
            raw = bytes(mime.data("text/uri-list")).decode("utf-8", errors="ignore")
        except Exception:
            raw = ""
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            u = QUrl(line)
            if u.isLocalFile():
                p = os.path.normpath(u.toLocalFile())
                low = p.lower()
                if low.endswith((".cbz", ".cbr")) and os.path.isfile(p) and p not in seen:
                    seen.add(p)
                    out.append(p)
    return out


class ClickableLabel(QLabel):
    """QLabel that emits a signal when clicked."""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ReadingDropListWidget(QListWidget):
    """List widget that accepts drag-and-drop of comic files and folders."""

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setStyleSheet("background-color: #21222c; border: 1px solid #44475a; color: white; font-size: 14px; padding: 5px;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in self.selectedItems():
                self.takeItem(self.row(item))
        super().keyPressEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isfile(path) and path.lower().endswith(('.cbz', '.cbr')):
                    self.add_comic_path(path)
                elif os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for f in sorted(files, key=natural_sort_key):
                            if f.lower().endswith(('.cbz', '.cbr')):
                                self.add_comic_path(os.path.join(root, f))
        else:
            super().dropEvent(event)

    def add_comic_path(self, path):
        parsed = parse_comic_filename(path)
        item = QListWidgetItem(parsed["display"])
        item.setData(Qt.ItemDataRole.UserRole, {
            "series": parsed["series"],
            "issue": parsed["issue"],
            "year": parsed["year"],
            "volume": parsed.get("volume") or "",
        })
        self.addItem(item)


class DraggableSearchList(QListWidget):
    """List widget that supports dragging items as file URLs."""

    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setStyleSheet("background-color: #21222c; border: 1px solid #44475a; color: white; padding: 5px;")

    def mimeData(self, items):
        mime = QMimeData()
        urls = []
        for item in items:
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                urls.append(QUrl.fromLocalFile(path))
        mime.setUrls(urls)
        return mime


class DraggableFolderComicList(QListWidget):
    """Lists comic files in a folder; drag onto CBL grid tiles to link (file URLs in mime data)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setAlternatingRowColors(False)
        self.setStyleSheet(
            "background-color: #21222c; border: 1px solid #44475a; color: #f8f8f2; "
            "font-size: 13px; padding: 4px;"
        )

    def mimeData(self, items):
        mime = QMimeData()
        urls = []
        for item in items:
            path = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(path, str) and path.lower().endswith((".cbz", ".cbr")):
                urls.append(QUrl.fromLocalFile(path))
        mime.setUrls(urls)
        return mime


class FolderComicsWindow(QMainWindow):
    """Secondary window: all .cbz/.cbr under a folder for dragging onto the CBL grid."""

    def __init__(self, folder_path: str, parent=None):
        super().__init__(parent)
        folder_path = os.path.normpath(folder_path)
        self.setWindowTitle(f"Folder comics — {os.path.basename(folder_path) or folder_path}")
        if os.path.isfile(APP_ICON_PATH):
            self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.resize(560, 640)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        hint = QLabel(
            "Drag one or more files onto a tile in the main window’s reading list grid to link or replace.\n"
            f"Folder:\n{folder_path}"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6272a4; padding: 4px;")
        layout.addWidget(hint)
        self.file_list = DraggableFolderComicList()
        layout.addWidget(self.file_list, 1)
        comics = []
        try:
            for root, _, files in os.walk(folder_path):
                for f in files:
                    if f.lower().endswith((".cbz", ".cbr")):
                        comics.append(os.path.normpath(os.path.join(root, f)))
        except OSError as e:
            log.warning("FolderComicsWindow scan failed: %s", e)
        comics.sort(key=natural_sort_key)
        for p in comics:
            try:
                rel = os.path.relpath(p, folder_path)
            except ValueError:
                rel = os.path.basename(p)
            it = QListWidgetItem(rel)
            it.setToolTip(p)
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.file_list.addItem(it)
        if not comics:
            ph = QListWidgetItem("(No .cbz / .cbr files in this folder)")
            ph.setFlags(Qt.ItemFlag.NoItemFlags)
            self.file_list.addItem(ph)


class HoverSummaryList(QListWidget):
    """QListWidget that shows a comic summary popup after hovering for 2.5 seconds."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._show_summary_popup)
        self._hovered_item = None
        self._popup = None
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        item = self.itemAt(event.pos())
        try:
            same = (item == self._hovered_item)
        except RuntimeError:
            same = False
        if not same:
            self._hover_timer.stop()
            self._close_popup()
            self._hovered_item = item
            if item:
                self._hover_timer.start(2500)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_timer.stop()
        self._close_popup()
        self._hovered_item = None
        super().leaveEvent(event)

    def _close_popup(self):
        if self._popup:
            try:
                self._popup.close()
            except RuntimeError:
                pass
            self._popup = None

    def _show_summary_popup(self):
        item = self._hovered_item
        if not item:
            return
        try:
            user_str = str(item.data(Qt.ItemDataRole.UserRole) or "")
        except RuntimeError:
            self._hovered_item = None
            return
        if not user_str or user_str.startswith("MISSING:") or user_str.startswith("NOTE:"):
            return

        if user_str.startswith("FOLDER:"):
            folder_path = user_str[7:]
            target_comic = None
            try:
                files = os.listdir(folder_path)
                files.sort(key=natural_sort_key)
                for f in files:
                    if f.lower().endswith(('.cbz', '.cbr')):
                        target_comic = os.path.join(folder_path, f)
                        break
            except Exception as _e:
                log.warning("Folder hover scan failed: %s", _e)
            if not target_comic:
                return
            user_str = target_comic
            title = os.path.basename(folder_path)
        else:
            title = os.path.splitext(os.path.basename(user_str))[0]

        summary = ""
        try:
            if user_str.lower().endswith(".cbz"):
                with zipfile.ZipFile(user_str, "r") as zf:
                    xml_name = next((n for n in zf.namelist() if n.lower() == "comicinfo.xml"), None)
                    if xml_name:
                        raw = zf.read(xml_name).decode("utf-8", errors="ignore")
                        raw = re.sub(r'\sxmlns="[^"]+"', '', raw, count=1)
                        root = ET.fromstring(raw)
                        summary = root.findtext("Summary", "").strip()
                        t = root.findtext("Title", "").strip()
                        s = root.findtext("Series", "").strip()
                        n = root.findtext("Number", "").strip()
                        if s:
                            title = f"{s} #{n}" if n else s
                        if t:
                            title += f" — {t}"
            elif user_str.lower().endswith(".cbr") and HAS_RAR:
                with rarfile.RarFile(user_str, "r") as rf:
                    xml_name = next((n for n in rf.namelist() if n.lower() == "comicinfo.xml"), None)
                    if xml_name:
                        raw = rf.read(xml_name).decode("utf-8", errors="ignore")
                        raw = re.sub(r'\sxmlns="[^"]+"', '', raw, count=1)
                        root = ET.fromstring(raw)
                        summary = root.findtext("Summary", "").strip()
        except Exception as _e:
            log.warning("HoverSummaryList XML read failed: %s", _e)

        if not summary:
            summary = "(No summary available)"

        self._close_popup()
        popup = QDialog(self, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        popup.setStyleSheet("""
            QDialog {
                background-color: #282a36;
                border: 1px solid #6272a4;
                border-radius: 6px;
            }
            QLabel { color: #f8f8f2; padding: 0; }
        """)
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #8be9fd; font-weight: bold; font-size: 13px;")
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        wrapped = "\n".join(textwrap.wrap(summary, width=60))
        body_lbl = QLabel(wrapped)
        body_lbl.setWordWrap(True)
        body_lbl.setMaximumWidth(420)
        layout.addWidget(body_lbl)

        popup.adjustSize()

        cursor_pos = self.mapToGlobal(self.viewport().mapFromGlobal(self.cursor().pos()))
        screen = QApplication.primaryScreen().availableGeometry()
        px = min(cursor_pos.x() + 16, screen.right() - popup.width() - 8)
        py = min(cursor_pos.y() + 16, screen.bottom() - popup.height() - 8)
        popup.move(px, py)
        popup.show()
        self._popup = popup


class CblGridList(HoverSummaryList):
    """CBL grid: drop .cbz/.cbr onto a tile (folder comic list window or Explorer)."""

    comic_file_dropped = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        # QAbstractItemView defaults to NoDragDrop, which blocks external file drops.
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def _cbl_drop_allowed(self) -> bool:
        win = self.window()
        fn = getattr(win, "_cbl_grid_accepts_manual_links", None)
        return callable(fn) and fn()

    def dragEnterEvent(self, event):
        if not self._cbl_drop_allowed():
            event.ignore()
            return
        if _mime_local_comic_paths(event.mimeData()):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        if not self._cbl_drop_allowed():
            event.ignore()
            return
        if _mime_local_comic_paths(event.mimeData()):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return
        event.ignore()

    def dropEvent(self, event):
        if not self._cbl_drop_allowed():
            event.ignore()
            return
        paths = _mime_local_comic_paths(event.mimeData())
        if not paths:
            event.ignore()
            return
        pos = event.position().toPoint()
        pt = self.viewport().mapFrom(self, pos)
        item = self.itemAt(pt)
        if item is None:
            event.ignore()
            return
        self.comic_file_dropped.emit(paths[0], item)
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
