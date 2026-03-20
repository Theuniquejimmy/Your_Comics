"""Custom Qt widgets for ComicVault."""
import os
import re
import textwrap
import zipfile
import xml.etree.ElementTree as ET

from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QLabel,
    QListWidget, QListWidgetItem, QVBoxLayout,
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QMimeData, pyqtSignal

from config import log
from utils import parse_comic_filename, natural_sort_key

try:
    import rarfile
    HAS_RAR = True
except ImportError:
    HAS_RAR = False


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
        if not user_str or user_str.startswith("MISSING:"):
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
