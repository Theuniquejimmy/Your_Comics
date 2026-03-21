"""UI components extracted from 200.py - dialogs, tabs, and ComicBrowser."""
import os
import re
import json
import html
import difflib
import textwrap
import datetime
import subprocess
import hashlib
import requests
import tempfile
import urllib.parse
import zipfile
import shutil
import xml.etree.ElementTree as ET
import markdown
from ebooklib import epub

try:
    import rarfile
    rarfile.UNRAR_TOOL = r"C:\Program Files\WinRAR\UnRAR.exe"
except ImportError:
    rarfile = None

import config
from config import (
    APP_SETTINGS,
    COMIC_VINE_KEY,
    GEMINI_KEY,
    CACHE_DIR,
    FOLLOWED_SERIES_FILE,
    PUB_COLOURS,
    log,
)
from utils import (
    natural_sort_key,
    generate_comicinfo_xml,
    parse_comic_filename,
    parse_comic_filename_full,
    inject_metadata_into_cbz,
    pub_info,
    force_remove_readonly,
)
from workers import (
    MiniImageFetcher,
    MiniAITaggerThread,
    ComicVineIssueThread,
    ComicConverterThread,
    NaturalSortProxyModel,
    FolderCoverLoaderThread,
    CoverLoaderThread,
    ComicVineSearchThread,
    ComicVineIssueSearchThread,
    ImageDownloadThread,
    MetadataInjectorThread,
    GeminiSummaryThread,
    GeminiChatThread,
    TTSWorkerThread,
    BatchProcessorThread,
    AIListGeneratorThread,
    DeepSearchThread,
    GithubCBLFetchThread,
    GithubCBLDownloadThread,
    GetComicsCheckThread,
    GCSitemapThread,
    GCCoverThread,
    gc_new_releases_thumb_path,
    gc_new_releases_uncache_thumb,
    BatchTaggerThread,
    HAS_RAR,
)
from widgets import (
    ClickableLabel,
    ReadingDropListWidget,
    DraggableSearchList,
    HoverSummaryList,
)

# Dracula-themed message boxes (default QMessageBox is light on many platforms).
DRACULA_MSGBOX_QSS = """
    QMessageBox { background-color: #282a36; color: #f8f8f2; }
    QMessageBox QLabel { color: #f8f8f2; }
    QPushButton {
        background-color: #44475a; color: #f8f8f2;
        padding: 5px 15px; border-radius: 3px; font-weight: bold;
    }
    QPushButton:hover { background-color: #6272a4; }
"""

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFileSystemModel,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PyQt6.QtCore import (
    Qt,
    QByteArray,
    QDir,
    QMimeData,
    QSize,
    QSortFilterProxyModel,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineDownloadRequest


# ==============================================================================
# BATCH COVER MATCH DIALOG
# ==============================================================================
class BatchCoverMatchDialog(QDialog):
    def __init__(self, filename, results, local_cover_bytes, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"ComicVine Cover Matcher - {filename}")
        self.resize(850, 600)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background-color: #282a36; color: #f8f8f2; }
            QLabel { color: #f8f8f2; font-weight: bold; }
            QLineEdit { background-color: #21222c; border: 1px solid #44475a; padding: 5px; color: #f8f8f2; }
            QListWidget { background-color: #21222c; border: 1px solid #44475a; color: white; font-size: 14px; padding: 5px;}
            QListWidget::item:selected { background-color: #6272a4; }
        """)

        self.results = results
        self.selected_data = None
        self.img_thread = None
        self.search_thread = None

        self.layout = QVBoxLayout(self)
        self.h_layout = QHBoxLayout()

        self.local_vbox = QVBoxLayout()
        self.local_vbox.addWidget(QLabel("Your Local Cover:"))
        self.local_cover_label = QLabel()
        self.local_cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.local_cover_label.setFixedSize(250, 380)

        if local_cover_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(local_cover_bytes)
            self.local_cover_label.setPixmap(pixmap.scaled(250, 380, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.local_cover_label.setText("No local cover found.")

        self.local_vbox.addWidget(self.local_cover_label)
        self.local_vbox.addStretch()
        self.h_layout.addLayout(self.local_vbox)

        self.center_vbox = QVBoxLayout()
        self.center_vbox.addWidget(QLabel("Search ComicVine for Issue:"))
        search_hbox = QHBoxLayout()
        self.search_input = QLineEdit()

        base_name = os.path.splitext(filename)[0]
        parsed = parse_comic_filename_full(base_name)
        series = parsed.get('series', '')
        issue = parsed.get('issue', '')
        year = parsed.get('year', '')
        sub = parsed.get('subtitle', '')
        if issue:
            clean_query = f"{series} {issue} {year}".strip()
        elif sub:
            clean_query = f"{series} {sub} {year}".strip()
        else:
            clean_query = f"{series} {year}".strip()
        self.search_input.setText(clean_query)

        self.search_btn = QPushButton("Search")
        self.search_btn.setStyleSheet("background-color: #44475a; color: white; padding: 5px; font-weight: bold;")
        self.search_btn.clicked.connect(self.perform_search)

        search_hbox.addWidget(self.search_input)
        search_hbox.addWidget(self.search_btn)
        self.center_vbox.addLayout(search_hbox)

        self.results_list = QListWidget()
        self.results_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_list.itemClicked.connect(self.on_result_clicked)

        self.center_vbox.addWidget(self.results_list)
        self.h_layout.addLayout(self.center_vbox, 1)

        self.remote_vbox = QVBoxLayout()
        self.remote_vbox.addWidget(QLabel("ComicVine Cover:"))
        self.remote_cover_label = QLabel("Select an issue\nto view cover.")
        self.remote_cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.remote_cover_label.setStyleSheet("border: 1px dashed #6272a4;")
        self.remote_cover_label.setFixedSize(250, 380)
        self.remote_vbox.addWidget(self.remote_cover_label)
        self.remote_vbox.addStretch()
        self.h_layout.addLayout(self.remote_vbox)

        self.layout.addLayout(self.h_layout)

        btn_layout = QHBoxLayout()
        self.skip_btn = QPushButton("⏭️ Skip File")
        self.skip_btn.setStyleSheet("background-color: #ff5555; color: #f8f8f2; font-weight: bold; padding: 10px;")
        self.skip_btn.clicked.connect(self.reject)

        self.ai_btn = QPushButton("🤖 Add AI Info")
        self.ai_btn.setStyleSheet("background-color: #bd93f9; color: #282a36; font-weight: bold; padding: 10px;")
        self.ai_btn.clicked.connect(self.generate_ai_info)

        self.accept_btn = QPushButton("✅ Accept & Inject")
        self.accept_btn.setStyleSheet("background-color: #50fa7b; color: #282a36; font-weight: bold; padding: 10px;")
        self.accept_btn.clicked.connect(self.accept_match)
        self.accept_btn.setEnabled(False)

        btn_layout.addWidget(self.skip_btn)
        btn_layout.addWidget(self.ai_btn)
        btn_layout.addWidget(self.accept_btn)
        self.layout.addLayout(btn_layout)

        self.populate_list(self.results)

    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self.results_list.clear()
        self.results_list.addItem("🔍 Searching Comic Vine...")
        self.search_btn.setEnabled(False)
        self.accept_btn.setEnabled(False)
        self.remote_cover_label.setText("Waiting for results...")

        m = re.search(r'4000-\d+', query) if 'comicvine.gamespot.com' in query.lower() else None
        if m:
            issue_id = m.group(0)
            api_url = f"https://comicvine.gamespot.com/api/issue/{issue_id}/"
            self.search_thread = ComicVineIssueThread(direct_api_url=api_url)
            self.search_thread.issue_ready.connect(self._on_direct_issue_loaded)
            self.search_thread.start()
        else:
            self.search_thread = ComicVineIssueSearchThread(query)
            self.search_thread.results_ready.connect(self.on_search_done)
            self.search_thread.start()

    def _on_direct_issue_loaded(self, issue_data):
        self.search_thread = None
        self.search_btn.setEnabled(True)
        results = [issue_data] if issue_data else []
        self.results = results
        self.populate_list(results)

    def on_search_done(self, new_results):
        self.search_btn.setEnabled(True)
        self.results = new_results
        self.populate_list(new_results)

    def populate_list(self, results):
        self.results_list.clear()
        if not results:
            self.results_list.addItem("❌ No issues found.")
            self.results_list.addItem("Use 🤖 Add AI Info below to generate metadata.")
            return

        for issue in results:
            vol_name = issue.get('volume', {}).get('name', 'Unknown Volume') if issue.get('volume') else 'Unknown Volume'
            issue_num = issue.get('issue_number', '?')
            name = issue.get('name', '')
            date = issue.get('cover_date', 'Unknown Date')

            display_text = f"{vol_name} #{issue_num}\nDate: {date}"
            if name:
                display_text += f"\nArc: {name}"
            self.results_list.addItem(display_text + "\n")
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)
            self.on_result_clicked(self.results_list.item(0))

    def on_result_clicked(self, item):
        idx = self.results_list.row(item)
        if idx >= len(self.results) or not self.results:
            return

        issue_stub = self.results[idx]
        image_data = issue_stub.get('image')
        img_url = image_data.get('medium_url') if isinstance(image_data, dict) else None

        self.remote_cover_label.setText("Downloading...")
        self.accept_btn.setEnabled(False)
        self.selected_data = issue_stub

        if img_url:
            self.img_thread = MiniImageFetcher(img_url)
            self.img_thread.image_ready.connect(self.show_remote_image)
            self.img_thread.start()
        else:
            self.remote_cover_label.setText("No cover available.")
            self.accept_btn.setEnabled(True)

    def show_remote_image(self, data):
        if data:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            self.remote_cover_label.setPixmap(pixmap.scaled(250, 380, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.remote_cover_label.setText("Image failed to load.")
        self.accept_btn.setEnabled(True)

    def accept_match(self):
        self.accept()

    def generate_ai_info(self):
        query = self.search_input.text().strip()
        if not query:
            return

        self.ai_btn.setEnabled(False)
        self.accept_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.ai_btn.setText("🤖 Generating...")
        self.remote_cover_label.setText("AI is working\nmagic...")

        self.ai_thread = MiniAITaggerThread(query)
        self.ai_thread.ai_ready.connect(self.on_ai_success)
        self.ai_thread.error_signal.connect(self.on_ai_error)
        self.ai_thread.start()

    def on_ai_success(self, ai_data):
        self.selected_data = ai_data
        self.accept()

    def on_ai_error(self, error_msg):
        self.ai_btn.setText("❌ AI Error")
        self.ai_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.remote_cover_label.setText(f"Error:\n{error_msg}")
        if self.results_list.currentItem():
            self.accept_btn.setEnabled(True)


# ==============================================================================
# LIST MAKER TAB
# ==============================================================================
class ListMakerTab(QWidget):
    def __init__(self, file_system_model):
        super().__init__()
        self.file_system_model = file_system_model

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        left_vbox = QWidget()
        left_layout = QVBoxLayout(left_vbox)
        left_layout.setContentsMargins(0, 0, 0, 10)
        left_layout.addWidget(QLabel("📂 Your Libraries (Drag to Right):"))

        self.lib_combo = QComboBox()
        self.lib_combo.setStyleSheet("background-color: #21222c; border: 1px solid #44475a; color: white; padding: 5px;")
        self.lib_combo.currentIndexChanged.connect(self.on_library_changed)
        left_layout.addWidget(self.lib_combo)

        self.local_search_input = QLineEdit()
        self.local_search_input.setPlaceholderText("Search entire library (Press Enter)...")
        self.local_search_input.setStyleSheet("background-color: #21222c; border: 1px solid #44475a; color: white; padding: 5px; margin-top: 5px;")
        self.local_search_input.returnPressed.connect(self.perform_library_search)
        left_layout.addWidget(self.local_search_input)

        self.search_results_list = DraggableSearchList()
        self.search_results_list.hide()

        self.tree = QTreeView()
        self.tree.setModel(self.file_system_model)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setDragEnabled(True)
        self.tree.setStyleSheet("background-color: #21222c; border: 1px solid #44475a; color: white;")
        left_layout.addWidget(self.tree)

        right_vbox = QWidget()
        right_layout = QVBoxLayout(right_vbox)
        right_layout.setContentsMargins(0, 0, 0, 10)

        dt_header_layout = QHBoxLayout()
        dt_label = QLabel("📚 DieselTech's CBLs")
        dt_label.setStyleSheet("color: #ffb86c; font-weight: bold; font-size: 13px;")
        dt_header_layout.addWidget(dt_label)
        dt_header_layout.addStretch()

        dt_nav_layout = QHBoxLayout()
        self.dt_back_btn = QPushButton("⬆ Up")
        self.dt_back_btn.setFixedWidth(55)
        self.dt_back_btn.setEnabled(False)
        self.dt_back_btn.setStyleSheet("background-color: #44475a; color: white; padding: 3px;")
        self.dt_back_btn.clicked.connect(self._dt_go_up)
        self.dt_path_label = QLabel("(not loaded)")
        self.dt_path_label.setStyleSheet("color: #6272a4; font-size: 11px;")
        self.dt_path_label.setWordWrap(True)
        dt_nav_layout.addWidget(self.dt_back_btn)
        dt_nav_layout.addWidget(self.dt_path_label, 1)

        self.dt_list = QListWidget()
        self.dt_list.setFixedHeight(160)
        self.dt_list.setStyleSheet(
            "background-color: #21222c; border: 1px solid #44475a; "
            "color: #f8f8f2; font-size: 12px; padding: 3px;"
        )
        self.dt_list.itemDoubleClicked.connect(self._dt_item_double_clicked)

        dt_action_layout = QHBoxLayout()
        self.dt_status_label = QLabel("Click to load")
        self.dt_status_label.setStyleSheet("color: #6272a4; font-size: 11px;")
        self.dt_status_label.mousePressEvent = lambda _: self._dt_fetch("")
        self.dt_status_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.dt_download_btn = QPushButton("📥 Download CBL")
        self.dt_download_btn.setEnabled(False)
        self.dt_download_btn.setStyleSheet(
            "background-color: #50fa7b; color: #282a36; font-weight: bold; padding: 4px 10px;"
        )
        self.dt_download_btn.clicked.connect(self._dt_download)
        dt_action_layout.addWidget(self.dt_status_label, 1)
        dt_action_layout.addWidget(self.dt_download_btn)

        right_layout.addLayout(dt_header_layout)
        right_layout.addLayout(dt_nav_layout)
        right_layout.addWidget(self.dt_list)
        right_layout.addLayout(dt_action_layout)

        self._dt_current_path = ""
        self._dt_path_stack = []
        self._dt_items = []
        self._dt_fetch_thread = None
        self._dt_dl_thread = None
        self._dt_selected_item = None

        right_layout.addWidget(QLabel("📋 Your Active Reading List (Drag to Reorder):"))
        self.active_list = ReadingDropListWidget()
        right_layout.addWidget(self.active_list)

        self.splitter.addWidget(left_vbox)
        self.splitter.addWidget(right_vbox)
        self.splitter.setSizes([300, 400])
        self.layout.addWidget(self.splitter, 1)

        ai_layout = QHBoxLayout()
        ai_layout.addWidget(QLabel("🤖 Ask AI to make me a list:"))
        self.ai_input = QLineEdit()
        self.ai_input.setPlaceholderText("e.g. Marvel Civil War Main Event, or Batman Knightfall...")
        self.ai_input.returnPressed.connect(self.generate_ai_list)

        self.ai_btn = QPushButton("Go")
        self.ai_btn.setStyleSheet("background-color: #bd93f9; color: #282a36; font-weight: bold;")
        self.ai_btn.clicked.connect(self.generate_ai_list)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #f1fa8c;")
        ai_layout.addWidget(self.ai_input)
        ai_layout.addWidget(self.ai_btn)
        ai_layout.addWidget(self.status_label)
        self.layout.addLayout(ai_layout)

        bottom_layout = QHBoxLayout()
        self.clear_btn = QPushButton("🗑️ Clear List")
        self.clear_btn.clicked.connect(self.active_list.clear)

        self.make_cbl_btn = QPushButton("💾 Make .cbl")
        self.make_cbl_btn.setStyleSheet("background-color: #50fa7b; color: #282a36; font-weight: bold; padding: 10px;")
        self.make_cbl_btn.clicked.connect(self.save_cbl)

        bottom_layout.addWidget(self.clear_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.make_cbl_btn)
        self.layout.addLayout(bottom_layout)

        self.ai_thread = None
        self.load_libraries()

    def _dt_fetch(self, path: str):
        self.dt_status_label.setText("⏳ Loading...")
        self.dt_list.clear()
        self.dt_download_btn.setEnabled(False)
        self._dt_selected_item = None
        self._dt_fetch_thread = GithubCBLFetchThread(path)
        self._dt_fetch_thread.results_ready.connect(self._dt_on_results)
        self._dt_fetch_thread.error_signal.connect(self._dt_on_error)
        self._dt_fetch_thread.start()

    def _dt_on_results(self, items):
        self._dt_items = items
        self.dt_list.clear()
        if not items:
            self.dt_status_label.setText("(empty folder)")
            return
        for item in items:
            icon = "📁 " if item["type"] == "dir" else "📄 "
            entry = QListWidgetItem(icon + item["name"])
            entry.setData(Qt.ItemDataRole.UserRole, item)
            self.dt_list.addItem(entry)
        n_files = sum(1 for i in items if i["type"] == "file")
        n_folders = sum(1 for i in items if i["type"] == "dir")
        parts = []
        if n_folders:
            parts.append(f"{n_folders} folder{'s' if n_folders > 1 else ''}")
        if n_files:
            parts.append(f"{n_files} CBL{'s' if n_files > 1 else ''}")
        self.dt_status_label.setText(", ".join(parts) + " — double-click to open")

    def _dt_on_error(self, msg):
        self.dt_status_label.setText(f"❌ {msg}")

    def _dt_item_double_clicked(self, list_item):
        item = list_item.data(Qt.ItemDataRole.UserRole)
        if item["type"] == "dir":
            self._dt_path_stack.append(self._dt_current_path)
            self._dt_current_path = item["path"]
            self.dt_path_label.setText(item["path"])
            self.dt_back_btn.setEnabled(True)
            self.dt_download_btn.setEnabled(False)
            self._dt_selected_item = None
            self._dt_fetch(item["path"])
        else:
            self._dt_selected_item = item
            self.dt_download_btn.setEnabled(True)
            self.dt_status_label.setText(f"Selected: {item['name']}")

    def _dt_go_up(self):
        if not self._dt_path_stack:
            return
        parent = self._dt_path_stack.pop()
        self._dt_current_path = parent
        self.dt_path_label.setText(parent if parent else "(root)")
        self.dt_back_btn.setEnabled(bool(self._dt_path_stack))
        self.dt_download_btn.setEnabled(False)
        self._dt_selected_item = None
        self._dt_fetch(parent)

    def _dt_download(self):
        item = self._dt_selected_item
        if not item or not item.get("download_url"):
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save CBL File", item["name"],
            "ComicBookList Files (*.cbl)"
        )
        if not save_path:
            return
        self.dt_download_btn.setEnabled(False)
        self.dt_status_label.setText("⏳ Downloading...")
        self._dt_dl_thread = GithubCBLDownloadThread(item["download_url"], save_path)
        self._dt_dl_thread.finished.connect(self._dt_on_download_done)
        self._dt_dl_thread.error.connect(self._dt_on_error)
        self._dt_dl_thread.start()

    def _dt_on_download_done(self, path):
        self.dt_download_btn.setEnabled(True)
        self.dt_status_label.setText(f"✅ Saved: {os.path.basename(path)}")
        QMessageBox.information(
            self, "Downloaded",
            f"CBL saved to:\n{path}\n\nYou can now load it via the reading list panel."
        )

    def showEvent(self, event):
        if not self._dt_items and self._dt_fetch_thread is None:
            self._dt_fetch("")
            self.dt_path_label.setText("(root)")
        current_path = self.lib_combo.currentData()
        self.load_libraries()
        index = self.lib_combo.findData(current_path)
        if index >= 0:
            self.lib_combo.setCurrentIndex(index)
        super().showEvent(event)

    def load_libraries(self):
        self.lib_combo.blockSignals(True)
        self.lib_combo.clear()
        self.lib_combo.addItem("💻 All Drives (Root)", "")

        if os.path.exists("libraries.json"):
            try:
                with open("libraries.json", "r") as f:
                    paths = json.load(f)
                    for p in paths:
                        folder_name = os.path.basename(os.path.normpath(p))
                        self.lib_combo.addItem(f"📁 {folder_name}", p)
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
        self.lib_combo.blockSignals(False)
        self.on_library_changed()

    def on_library_changed(self, *args):
        if hasattr(self, 'local_search_input'):
            self.local_search_input.clear()
            self.search_results_list.hide()
            self.tree.show()

        path = self.lib_combo.currentData()
        if path and os.path.exists(path):
            self.tree.setRootIndex(self.file_system_model.index(path))
        else:
            self.tree.setRootIndex(self.file_system_model.index(""))

    def perform_library_search(self):
        query = self.local_search_input.text().strip()
        if not query:
            self.search_results_list.hide()
            self.tree.show()
            return

        self.tree.hide()
        self.search_results_list.show()
        self.search_results_list.clear()
        self.search_results_list.addItem("🔍 Deep Searching...")

        libraries = []
        for i in range(self.lib_combo.count()):
            path = self.lib_combo.itemData(i)
            if path:
                libraries.append(path)

        self.deep_search_thread = DeepSearchThread(query, libraries)
        self.deep_search_thread.results_ready.connect(self.on_search_done)
        self.deep_search_thread.start()

    def on_search_done(self, results):
        self.search_results_list.clear()
        if not results:
            self.search_results_list.addItem("❌ No results found.")
            return

        for res in results:
            prefix = "📁 " if res['is_folder'] else "📕 "
            item = QListWidgetItem(f"{prefix}{res['name']}")
            item.setData(Qt.ItemDataRole.UserRole, res['path'])
            item.setToolTip(res['path'])
            self.search_results_list.addItem(item)

    def generate_ai_list(self):
        query = self.ai_input.text().strip()
        if not query:
            return

        self.ai_btn.setEnabled(False)
        self.status_label.setText("⏳ AI is searching and compiling (this may take a moment for large lists)...")

        self.ai_thread = AIListGeneratorThread(query)
        self.ai_thread.list_ready.connect(self.on_ai_success)
        self.ai_thread.error_signal.connect(self.on_ai_error)
        self.ai_thread.start()

    def on_ai_success(self, response_data):
        self.ai_btn.setEnabled(True)
        description = response_data.get("description", "No description provided.")
        items = response_data.get("items", [])

        msg = QMessageBox(self)
        msg.setWindowTitle("AI Reading List Generated")
        msg.setText("Here is the list I put together for you:")
        msg.setInformativeText(f"{description}\n\nTotal Issues/Books: {len(items)}\n\nDo you want to add this to your reading list?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        msg.setStyleSheet("""
            QMessageBox { background-color: #282a36; color: #f8f8f2; }
            QLabel { color: #f8f8f2; }
            QPushButton { background-color: #44475a; color: white; padding: 5px 15px; border-radius: 3px; font-weight: bold; }
            QPushButton:hover { background-color: #6272a4; }
        """)

        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.status_label.setText(f"✅ AI added {len(items)} items!")
            for book in items:
                series = book.get('series', '')
                issue = book.get('issue', '')
                year = book.get('year', '')
                display = f"{series} #{issue}" if issue else series
                if year:
                    display += f" ({year})"
                item = QListWidgetItem(f"✨ {display}")
                item.setData(Qt.ItemDataRole.UserRole, {"series": series, "issue": issue, "year": year})
                self.active_list.addItem(item)
        else:
            self.status_label.setText("❌ AI list discarded by user.")

    def on_ai_error(self, err):
        self.ai_btn.setEnabled(True)
        self.status_label.setText(f"❌ AI Error: {err}")

    def save_cbl(self):
        if self.active_list.count() == 0:
            QMessageBox.warning(self, "Empty", "Add some comics to the list first!")
            return

        last_dir = APP_SETTINGS.get("last_cbl_dir", "")
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Reading List", os.path.join(last_dir, "My Reading List.cbl") if last_dir else "My Reading List.cbl",
            "ComicBookList Files (*.cbl)"
        )
        if not save_path:
            return

        APP_SETTINGS["last_cbl_dir"] = os.path.dirname(save_path)
        try:
            with open("settings.json", "w") as f:
                json.dump(APP_SETTINGS, f)
        except Exception as _e:
            log.warning("Suppressed exception: %s", _e)

        list_name = os.path.splitext(os.path.basename(save_path))[0]
        root = ET.Element("ReadingList", {"xmlns:xsd": "http://www.w3.org/2001/XMLSchema", "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"})
        ET.SubElement(root, "Name").text = list_name
        books_node = ET.SubElement(root, "Books")

        for i in range(self.active_list.count()):
            data = self.active_list.item(i).data(Qt.ItemDataRole.UserRole)
            if data:
                book_attrs = {"Series": data["series"]}
                if data["issue"]:
                    book_attrs["Number"] = data["issue"]
                if data["year"]:
                    book_attrs["Year"] = data["year"]
                ET.SubElement(books_node, "Book", book_attrs)

        tree = ET.ElementTree(root)
        try:
            ET.indent(tree, space="  ", level=0)
        except AttributeError:
            pass
        tree.write(save_path, encoding="utf-8", xml_declaration=True)
        QMessageBox.information(self, "Success", f"Saved list: {list_name}.cbl")


# ==============================================================================
# METADATA MATCH DIALOG
# ==============================================================================
class MetadataMatchDialog(QDialog):
    def __init__(self, filepath, local_pixmap):
        super().__init__()
        self.filepath = filepath

        self.setWindowTitle("ComicVine Cover Matcher")
        self.resize(800, 600)
        self.setStyleSheet("""
            QDialog { background-color: #282a36; color: #f8f8f2; }
            QLabel { color: #f8f8f2; font-weight: bold; }
            QLineEdit { background-color: #21222c; border: 1px solid #44475a; padding: 5px; color: #f8f8f2; }
            QPushButton { background-color: #44475a; color: white; padding: 6px; border-radius: 3px; }
            QPushButton:hover { background-color: #6272a4; }
            QPushButton#save_btn { background-color: #50fa7b; color: #282a36; font-weight: bold; }
            QListWidget { background-color: #21222c; border: 1px solid #44475a; color: white; }
        """)

        self.layout = QVBoxLayout(self)
        self.h_layout = QHBoxLayout()

        # Local Cover
        self.local_vbox = QVBoxLayout()
        self.local_vbox.addWidget(QLabel("Your Local Cover:"))
        self.local_cover_label = QLabel()
        self.local_cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.local_cover_label.setPixmap(local_pixmap.scaled(300, 450, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.local_vbox.addWidget(self.local_cover_label)
        self.h_layout.addLayout(self.local_vbox)

        # Search Center
        self.center_vbox = QVBoxLayout()
        self.center_vbox.addWidget(QLabel("Search ComicVine for Issue:"))

        search_hbox = QHBoxLayout()
        self.search_input = QLineEdit()
        base_name = os.path.splitext(os.path.basename(filepath))[0]

        _p   = parse_comic_filename_full(base_name)
        _s   = _p.get('series', '')
        _i   = _p.get('issue', '')
        _y   = _p.get('year', '')
        _sub = _p.get('subtitle', '')
        if _i:
            _query = f"{_s} {_i} {_y}".strip()
        elif _sub:
            _query = f"{_s} {_sub} {_y}".strip()
        else:
            _query = f"{_s} {_y}".strip()
        self.search_input.setText(_query)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.perform_search)
        search_hbox.addWidget(self.search_input)
        search_hbox.addWidget(self.search_btn)
        self.center_vbox.addLayout(search_hbox)

        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.on_result_clicked)
        self.center_vbox.addWidget(self.results_list)
        self.h_layout.addLayout(self.center_vbox)

        # Remote Cover
        self.remote_vbox = QVBoxLayout()
        self.remote_vbox.addWidget(QLabel("ComicVine Cover:"))
        self.remote_cover_label = QLabel("Select an issue\nto view cover.")
        self.remote_cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.remote_cover_label.setFixedSize(300, 450)
        self.remote_vbox.addWidget(self.remote_cover_label)
        self.h_layout.addLayout(self.remote_vbox)

        self.layout.addLayout(self.h_layout)

        btn_layout = QHBoxLayout()

        self.ai_btn = QPushButton("🤖 Add AI Info")
        self.ai_btn.setStyleSheet("background-color: #bd93f9; color: #282a36; font-weight: bold; padding: 10px;")
        self.ai_btn.clicked.connect(self.generate_ai_info)

        self.save_btn = QPushButton("✅ Inject Metadata into CBZ")
        self.save_btn.setObjectName("save_btn")
        self.save_btn.setStyleSheet("background-color: #50fa7b; color: #282a36; font-weight: bold; padding: 10px;")
        self.save_btn.clicked.connect(self.inject_metadata)
        self.save_btn.setEnabled(False)

        btn_layout.addWidget(self.ai_btn)
        btn_layout.addWidget(self.save_btn)
        self.layout.addLayout(btn_layout)

        self.current_results = []
        self.selected_issue_data = None
        self.search_thread = None
        self.img_thread = None
        self.issue_thread = None

        QTimer.singleShot(200, self.perform_search)

    def perform_search(self):
        query = self.search_input.text().strip()
        if not query: return
        self.results_list.clear()
        self.results_list.addItem("Searching...")
        self.search_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

        self.search_thread = ComicVineIssueSearchThread(query)
        self.search_thread.results_ready.connect(self.on_search_done)
        self.search_thread.start()

    def on_search_done(self, results):
        self.search_btn.setEnabled(True)
        self.results_list.clear()
        self.current_results = results

        if not results:
            self.results_list.addItem("No issues found.")
            return

        for issue in results:
            vol_name  = issue.get('volume', {}).get('name', 'Unknown Volume')
            issue_num = issue.get('issue_number', '')
            name      = issue.get('name', '')
            date      = issue.get('cover_date', '')
            arcs      = issue.get('story_arc_credits', [])
            arc_str   = arcs[0].get('name', '') if arcs else ''

            display = f"{vol_name} #{issue_num}" if issue_num else vol_name
            if name:    display += f" - {name}"
            if date:    display += f"\nDate: {date}"
            if arc_str: display += f"\nArc: {arc_str}"
            self.results_list.addItem(display)

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)
            self.on_result_clicked(self.results_list.item(0))

    def on_result_clicked(self, item):
        idx = self.results_list.row(item)
        if idx < 0 or idx >= len(self.current_results): return

        issue_stub = self.current_results[idx]
        img_url = issue_stub.get('image', {}).get('medium_url')

        self.remote_cover_label.setText("Loading match...")
        self.save_btn.setEnabled(False)

        if img_url:
            self.img_thread = ImageDownloadThread(img_url)
            self.img_thread.image_ready.connect(self.on_image_downloaded)
            self.img_thread.start()

        api_url = issue_stub.get('api_detail_url')
        if api_url:
            self.issue_thread = ComicVineIssueThread(direct_api_url=api_url)
            self.issue_thread.issue_ready.connect(self.on_full_data_ready)
            self.issue_thread.start()

    def on_image_downloaded(self, data):
        if data:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            self.remote_cover_label.setPixmap(pixmap.scaled(300, 450, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.remote_cover_label.setText("Image load failed.")

    def on_full_data_ready(self, data):
        self.selected_issue_data = data
        self.save_btn.setEnabled(True)

    def inject_metadata(self):
        if not self.selected_issue_data: return
        try:
            self.xml_string = self.build_xml()
            self.accept()
        except Exception as e:
            log.warning("Error building XML: %s", e)
            self.accept()

    def generate_ai_info(self):
        query = self.search_input.text().strip()
        if not query: return

        self.ai_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.ai_btn.setText("🤖 Generating...")
        self.remote_cover_label.setText("AI is working\nmagic...")

        self.ai_thread = MiniAITaggerThread(query)
        self.ai_thread.ai_ready.connect(self.on_ai_success)
        self.ai_thread.error_signal.connect(self.on_ai_error)
        self.ai_thread.start()

    def on_ai_success(self, ai_data):
        self.selected_issue_data = ai_data
        self.inject_metadata()

    def on_ai_error(self, error_msg):
        self.ai_btn.setText("❌ AI Error")
        self.ai_btn.setEnabled(True)
        self.remote_cover_label.setText(f"Error:\n{error_msg}")
        if self.results_list.currentItem():
            self.save_btn.setEnabled(True)

    def build_xml(self):
        data = self.selected_issue_data

        base_name = os.path.splitext(os.path.basename(self.filepath))[0]
        clean_name = re.sub(r'\(.*?\)|\[.*?\]', '', base_name).strip()
        m_vol_override = re.search(r'(?i)\b(?:v|vol|volume|book|bk|tpb)\.?\s*0*(\d+)', clean_name)
        is_volume = bool(m_vol_override)

        match = re.search(r'^(.*?)\s*#\s*(\d+)', clean_name)
        if not match: match = re.search(r'^(.*?)\s+(\d+)\s*$', clean_name)
        local_issue = m_vol_override.group(1) if is_volume else (str(int(match.group(2))) if match else "")
        final_number = local_issue if (is_volume and local_issue) else (str(data.get("issue_number") or "") or local_issue)

        title = html.escape(str(data.get("name") or ""))
        series = html.escape(str(data.get("volume", {}).get("name") or ""))

        desc = data.get("description") or data.get("deck") or ""
        desc = html.escape(re.sub(r'<[^>]+>', '', desc).strip())

        year, month, day = "", "", ""
        if data.get("cover_date"):
            parts = data.get("cover_date").split('-')
            if len(parts) >= 1: year = parts[0]
            if len(parts) >= 2: month = parts[1]
            if len(parts) >= 3: day = parts[2]

        writers, artists = [], []
        for person in data.get("person_credits", []):
            roles = person.get("role", "").lower()
            name = html.escape(person.get("name", ""))
            if "writer" in roles: writers.append(name)
            if any(r in roles for r in ["artist", "penciler", "penciller", "inker", "colorist"]): artists.append(name)

        story_arcs = [str(data.get("story_arc"))] if data.get("story_arc") else []
        for arc in data.get("story_arc_credits", []): story_arcs.append(arc.get("name", ""))

        characters = [html.escape(c['name']) for c in data.get('character_credits', [])]
        teams = [html.escape(t['name']) for t in data.get('team_credits', [])]
        locations = [html.escape(l['name']) for l in data.get('location_credits', [])]

        xml = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
            f'  <Title>{title}</Title>' if title else '',
            f'  <Series>{series}</Series>' if series else '',
            f'  <Number>{final_number}</Number>' if final_number else '',
            f'  <Summary>{desc}</Summary>' if desc else '',
            f'  <Year>{year}</Year>' if year else '',
            f'  <Month>{month}</Month>' if month else '',
            f'  <Day>{day}</Day>' if day else '',
            f'  <Writer>{", ".join(dict.fromkeys(writers))}</Writer>' if writers else '',
            f'  <Penciller>{", ".join(dict.fromkeys(artists))}</Penciller>' if artists else '',
            f'  <StoryArc>{", ".join(dict.fromkeys([html.escape(a) for a in story_arcs if a]))}</StoryArc>' if story_arcs else '',
            f'  <Characters>{", ".join(dict.fromkeys(characters))}</Characters>' if characters else '',
            f'  <Teams>{", ".join(dict.fromkeys(teams))}</Teams>' if teams else '',
            f'  <Locations>{", ".join(dict.fromkeys(locations))}</Locations>' if locations else '',
            '  <PlayCount>1</PlayCount>',
            '</ComicInfo>'
        ]
        return "\n".join(filter(None, xml))

# ==============================================================================
# COMIC FINDER TAB
# ==============================================================================
class ComicFinderTab(QWidget):
    analysis_completed = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)
        
        self.controls_panel = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_panel)
        
        self.controls_layout.addWidget(QLabel("🔍 Comic Vine Search"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter Series Name...")
        self.controls_layout.addWidget(self.search_input)
        self.search_input.returnPressed.connect(self.search_volumes)
        
        self.search_btn = QPushButton("Search Volumes")
        self.search_btn.clicked.connect(self.search_volumes)
        self.controls_layout.addWidget(self.search_btn)
        
        self.volume_combo = QComboBox()
        self.controls_layout.addWidget(self.volume_combo)
        self.current_volumes = {} 
        
        issue_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◄")
        self.prev_btn.setFixedWidth(30)
        self.prev_btn.clicked.connect(self.prev_issue)
        
        self.issue_input = QLineEdit("1")
        self.issue_input.setPlaceholderText("Issue #")
        self.issue_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.next_btn = QPushButton("►")
        self.next_btn.setFixedWidth(30)
        self.next_btn.clicked.connect(self.next_issue)

        issue_layout.addWidget(self.prev_btn)
        issue_layout.addWidget(self.issue_input)
        issue_layout.addWidget(self.next_btn)
        
        self.alt_name_input = QLineEdit()
        self.alt_name_input.setPlaceholderText("Wiki/Vol Override")
        
        self.controls_layout.addWidget(QLabel("Issue Selection:"))
        self.controls_layout.addLayout(issue_layout)
        self.controls_layout.addWidget(self.alt_name_input)
        
        self.analyze_btn = QPushButton("Analyze Single Issue")
        self.analyze_btn.clicked.connect(self.fetch_and_analyze)
        self.controls_layout.addWidget(self.analyze_btn)
        
        self.controls_layout.addSpacing(15)
        self.controls_layout.addWidget(QLabel("📦 Batch EPUB Processor"))
        
        batch_layout = QHBoxLayout()
        self.batch_range_input = QLineEdit()
        self.batch_range_input.setPlaceholderText("Range (e.g., 1-5)")
        self.batch_start_btn = QPushButton("Start Batch")
        self.batch_start_btn.clicked.connect(self.start_batch)
        batch_layout.addWidget(self.batch_range_input)
        batch_layout.addWidget(self.batch_start_btn)
        self.controls_layout.addLayout(batch_layout)
        
        self.batch_progress = QProgressBar()
        self.batch_progress.setValue(0)
        self.batch_progress.setTextVisible(True)
        self.controls_layout.addWidget(self.batch_progress)

        self.controls_layout.addSpacing(15)
        self.controls_layout.addWidget(QLabel("🎙️ Narrator Settings"))
        self.voice_combo = QComboBox()
        self.voices = {
            "Christopher (Deep US Male)": "en-US-ChristopherNeural", 
            "Aria (Clear US Female)": "en-US-AriaNeural",
            "Guy (Energetic US Male)": "en-US-GuyNeural",
            "Jenny (Standard US Female)": "en-US-JennyNeural",
            "Steffan (Pro US Male)": "en-US-SteffanNeural",
            "Ryan (British Male)": "en-GB-RyanNeural",
            "Sonia (British Female)": "en-GB-SoniaNeural",
            "Natasha (Australian Female)": "en-AU-NatashaNeural",
            "William (Australian Male)": "en-AU-WilliamNeural"
        }
        self.voice_combo.addItems(list(self.voices.keys()))
        self.controls_layout.addWidget(self.voice_combo)

        speed_layout = QHBoxLayout()
        self.speed_label = QLabel("Speed: 1.0x")
        self.speed_label.setFixedWidth(65)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(5, 20) 
        self.speed_slider.setValue(10)    
        self.speed_slider.valueChanged.connect(self.change_speed)
        speed_layout.addWidget(self.speed_label)
        speed_layout.addWidget(self.speed_slider)
        self.controls_layout.addLayout(speed_layout)

        self.audio_layout = QHBoxLayout()
        
        # Add the Play emoji!
        self.play_btn = QPushButton("▶️ Play Audio")
        self.play_btn.clicked.connect(self.play_audio)
        
        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setEnabled(False)
        
        # Add the Stop emoji!
        self.stop_btn = QPushButton("🛑 Stop")
        self.stop_btn.clicked.connect(self.stop_audio)
        
        self.autoplay_checkbox = QCheckBox("Auto-Play Next")
        self.autoplay_checkbox.setStyleSheet("color: #50fa7b; font-weight: bold;") # Give it a nice neon green pop!
        
        self.audio_layout.addWidget(self.play_btn)
        self.audio_layout.addWidget(self.pause_btn)
        self.audio_layout.addWidget(self.stop_btn)
        self.audio_layout.addWidget(self.autoplay_checkbox)
        self.controls_layout.addLayout(self.audio_layout)
        
        self.controls_layout.addStretch() 
        
        self.results_panel = QWidget()
        self.results_layout = QVBoxLayout(self.results_panel)
        
        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #f1fa8c;")
        self.results_layout.addWidget(self.status_label)
        
        self.cover_label = ClickableLabel()
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.cover_label.hide() # Keep it hidden until we have a comic!
        self.cover_label.clicked.connect(self.show_large_cover)
        self.results_layout.addWidget(self.cover_label)
        
        self.summary_display = QTextBrowser()
        self.summary_display.setOpenExternalLinks(False)
        self.results_layout.addWidget(self.summary_display)
        
        self.export_epub_btn = QPushButton("📖 Export Single Summary as EPUB")
        self.export_epub_btn.clicked.connect(self.export_epub)
        self.export_epub_btn.setEnabled(False)
        self.results_layout.addWidget(self.export_epub_btn)
        
        self.splitter.addWidget(self.controls_panel)
        self.splitter.addWidget(self.results_panel)
        self.splitter.setSizes([350, 650])
        
        self.current_issue_data = None
        self.current_summary_text = None
        self.current_title = None
        self.audio_temp_file = os.path.join(CACHE_DIR, "temp_audio.mp3")
        self.batch_thread = None
        

    def play_tts_audio(self, audio_file_path):
        # 1. Create the player (MUST be self. so it doesn't get deleted)
        self.media_player = QMediaPlayer()
        
        # 2. Create the speaker (MUST be self. so it doesn't get deleted)
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0) # Set volume to 100%
        
        # 3. Plug the speaker into the player
        self.media_player.setAudioOutput(self.audio_output)
        
        # 4. Load the file and press play!
        self.media_player.setSource(QUrl.fromLocalFile(audio_file_path))
        self.media_player.play()

    def change_speed(self, value):
        speed = value / 10.0
        # 1. Always update the visual label so you know what speed is set for the next track
        self.speed_label.setText(f"Speed: {speed}x")
        
        if hasattr(self, 'player') and self.player is not None:
            self.player.setPlaybackRate(speed)
    def _get_issue_int(self):
        try:
            val = int(self.issue_input.text().strip())
            return max(1, val)
        except ValueError:
            return 1

    def prev_issue(self):
        val = self._get_issue_int()
        if val > 1:
            self.issue_input.setText(str(val - 1))
            if self.volume_combo.currentText():
                self.fetch_and_analyze()

    def next_issue(self):
        val = self._get_issue_int()
        self.issue_input.setText(str(val + 1))
        if self.volume_combo.currentText():
            self.fetch_and_analyze()

    def search_volumes(self):
        query = self.search_input.text()
        if not query: return
        self.status_label.setText("Searching Comic Vine...")
        self.search_btn.setEnabled(False)
        
        self.search_thread = ComicVineSearchThread(query)
        self.search_thread.results_ready.connect(self.on_volumes_found)
        self.search_thread.start()

    def on_volumes_found(self, results):
        self.search_btn.setEnabled(True)
        self.volume_combo.clear()
        self.current_volumes.clear()
        
        if not results:
            self.status_label.setText("No volumes found.")
            return

        # 1. SORT THE RESULTS chronologically
        # If 'start_year' is missing or None, we default to '9999' so those unknowns drop to the very bottom of the list.
        sorted_results = sorted(results, key=lambda v: str(v.get('start_year') or '9999'))
            
        # 2. POPULATE THE DROPDOWN using the sorted list
        for v in sorted_results:
            year = v.get('start_year') or 'Unknown'
            name = f"{v['name']} ({year})"
            
            self.current_volumes[name] = v['id']
            self.volume_combo.addItem(name)
            
        self.status_label.setText(f"Found {len(sorted_results)} volumes.")

    def fetch_and_analyze(self):
        # --- NEW: Safely silence any playing audio immediately! ---
        if hasattr(self, 'player') and self.player is not None:
            self.player.stop()
            # Reset the pause button so it doesn't get visually stuck
            if hasattr(self, 'pause_btn'):
                self.pause_btn.setEnabled(False)
                self.pause_btn.setText("⏸️ Pause")

        # --- Your existing code continues here ---
        self.issue_input.setText(str(self._get_issue_int()))
        
        vol_name = self.volume_combo.currentText()
        if not vol_name: return
        
        vol_id = self.current_volumes[vol_name]
        issue_num = self.issue_input.text()
        alt_name = self.alt_name_input.text()
        self.current_title = f"{vol_name} #{issue_num}"
        
        self.status_label.setText(f"Fetching Issue {issue_num} data...")
        self.analyze_btn.setEnabled(False)
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        
        self.issue_thread = ComicVineIssueThread(vol_id, issue_num)
        self.issue_thread.issue_ready.connect(self.on_issue_data)
        self.issue_thread.start()

    def on_issue_data(self, data):
        if not data:
            self.status_label.setText("Issue not found on Comic Vine.")
            self.analyze_btn.setEnabled(True)
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(True)
            return
            
        self.current_issue_data = data
        self.status_label.setText("Generating AI Summary...")
        
        # --- NEW: Start downloading the cover image! ---
        img_url = data.get('image', {}).get('medium_url')
        if img_url:
            self.cover_label.setText("Loading cover...")
            self.cover_label.show()
            self.img_thread = ImageDownloadThread(img_url)
            self.img_thread.image_ready.connect(self.on_cover_downloaded)
            self.img_thread.start()
        else:
            self.cover_label.hide()
        
        vol_name = self.volume_combo.currentText().split(' (')[0]
        issue_num = self.issue_input.text()
        alt_name = self.alt_name_input.text()
        
        self.summary_thread = GeminiSummaryThread(data, vol_name, issue_num, alt_name)
        self.summary_thread.summary_ready.connect(self.on_summary_ready)
        self.summary_thread.start()

    def on_summary_ready(self, summary_text):
        self.current_summary_text = summary_text
        html = markdown.markdown(summary_text)
        self.summary_display.setHtml(f"<h2>{self.current_title}</h2>" + html)
        self.export_epub_btn.setEnabled(True)
        
        self.analysis_completed.emit(self.current_title, summary_text)
        
        self.status_label.setText("Generating Audio TTS...")
        voice_id = self.voices[self.voice_combo.currentText()]
        
        # --- NEW: Strip formatting symbols to prevent the TTS from choking ---
        clean_text = re.sub(r'[*_#`~>|-]', '', summary_text) # Remove markdown characters
        clean_text = clean_text.replace('\n', ' ') # Replace hard returns with spaces
        clean_text = " ".join(clean_text.split()) # Consolidate multiple spaces into one
        
        # Use the clean_text for the TTS engine!
        self.tts_thread = TTSWorkerThread(clean_text, voice_id)
        self.tts_thread.audio_ready.connect(self.on_audio_ready)
        self.tts_thread.start()

    def play_audio(self):
        # 1. Does the player exist? (Meaning we've loaded audio at least once)
        if hasattr(self, 'player') and self.player is not None:
            # 2. Does the file we want to play actually exist?
            if hasattr(self, 'audio_temp_file') and os.path.exists(self.audio_temp_file):
                self.pause_btn.setEnabled(True)
                self.pause_btn.setText("⏸️ Pause")
                self.player.play()
        else:
            # Optional: Add a status message so the user knows they have to fetch a comic first!
            self.status_label.setText("No audio loaded yet. Please analyze a comic first!")
            
    def stop_audio(self):
        # Safety constraint: Only try to stop the player if there's actually a player
        if not hasattr(self, 'player') or self.player is None:
            return 
            
        self.player.stop()
        
        if hasattr(self, 'pause_btn'):
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("⏸️ Pause")

    def on_audio_ready(self, audio_data):

        # Clear the "Generating" status so you know it finished!
        self.status_label.setText("Audio Ready! Playing...")

        # 1. Safely check if the player exists before trying to stop it
        if hasattr(self, 'player') and self.player is not None:
            self.player.stop()

        # 2. Save the raw audio bytes into a temporary MP3 file
        temp_audio_path = os.path.join(tempfile.gettempdir(), "temp_comic_audio.mp3")
        with open(temp_audio_path, 'wb') as f:
            f.write(audio_data)

        # 3. Create the player and speaker (attached to 'self')
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0) 
        
        # 4. Plug the speaker into the player
        self.player.setAudioOutput(self.audio_output)
        
        # 5. Load the new temporary file and press play!
        self.player.setSource(QUrl.fromLocalFile(temp_audio_path))
        self.player.mediaStatusChanged.connect(self.check_autoplay)
        self.player.play()
        
        
        # 6. Wake the buttons back up so you can actually click them!
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.analyze_btn.setEnabled(True)
        self.prev_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
    

    # ⬅️ Look at this alignment! It must line up perfectly with 'def on_audio_ready'
    def toggle_pause(self):
        # Safety constraint: Check if the player actually exists
        if not hasattr(self, 'player') or self.player is None:
            return 

        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.pause_btn.setText("▶️ Resume")
        else:
            self.player.play()
            self.pause_btn.setText("⏸️ Pause")

    def check_autoplay(self, status):
        
        # Did the track naturally finish playing all the way to the end?
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Is the Auto-Play box checked?
            if hasattr(self, 'autoplay_checkbox') and self.autoplay_checkbox.isChecked():
                self.status_label.setText("Track finished! Auto-playing next issue...")
                
                # Make sure the buttons disable so the user knows it's working
                self.analyze_btn.setEnabled(False)
                self.prev_btn.setEnabled(False)
                self.next_btn.setEnabled(False)
                
                # Trigger the next issue jump!
                self.next_issue()
    
    def export_epub(self):
        if not self.current_summary_text: return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save EPUB", f"{self.current_title}.epub", "EPUB Files (*.epub)")
        if not save_path: return
        
        cover_url = self.current_issue_data.get('image', {}).get('medium_url')
        try:
            book = epub.EpubBook()
            book.set_identifier(self.current_title.replace(" ", "_").replace("#", ""))
            book.set_title(self.current_title)
            book.set_language('en')
            book.add_author("Comic Vault Analyzer")
            
            if cover_url:
                try:
                    img_data = requests.get(cover_url).content
                    book.set_cover("cover.jpg", img_data)
                except Exception as _e:
                    log.warning("Suppressed exception: %s", _e)
            c1 = epub.EpubHtml(title=self.current_title, file_name='chap_01.xhtml', lang='en')
            c1.content = f'<h2>{self.current_title}</h2>' + markdown.markdown(self.current_summary_text)
            book.add_item(c1)
            book.toc = (epub.Link('chap_01.xhtml', self.current_title, 'intro'),)
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())
            book.spine = ['nav', c1]
            
            epub.write_epub(save_path, book)
            QMessageBox.information(self, "Success", f"EPUB saved successfully to:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save EPUB:\n{str(e)}")

    def start_batch(self):
        b_range = self.batch_range_input.text()
        vol_name = self.volume_combo.currentText()
        if not vol_name or "-" not in b_range:
            QMessageBox.warning(self, "Warning", "Please select a volume and format the range properly (e.g., 1-5).")
            return
            
        try:
            start_num, end_num = map(int, b_range.split('-'))
        except ValueError:
            QMessageBox.warning(self, "Warning", "Range must be two numbers separated by a hyphen.")
            return

        vol_id = self.current_volumes[vol_name]
        alt_name = self.alt_name_input.text()

        output_dir = QFileDialog.getExistingDirectory(self, "Select Folder to Save EPUBs")
        if not output_dir: return

        self.batch_start_btn.setEnabled(False)
        self.batch_progress.setValue(0)
        
        self.batch_thread = BatchProcessorThread(vol_id, vol_name, alt_name, start_num, end_num, output_dir)
        self.batch_thread.progress_update.connect(self.on_batch_progress)
        self.batch_thread.log_update.connect(self.on_batch_log)
        self.batch_thread.finished_batch.connect(self.on_batch_finished)
        self.batch_thread.start()

    def on_batch_progress(self, current, total):
        percentage = int((current / total) * 100)
        self.batch_progress.setValue(percentage)

    def on_batch_log(self, message):
        self.status_label.setText(f"Batch: {message}")
        self.summary_display.append(f"<p style='color:#8be9fd;'>{message}</p>")

    def on_batch_finished(self, folder_path):
        self.batch_start_btn.setEnabled(True)
        self.batch_progress.setValue(100)
        self.status_label.setText("Batch processing complete!")
        QMessageBox.information(self, "Batch Finished", f"All summaries successfully saved to:\n{folder_path}")
    
    def on_cover_downloaded(self, image_data):
        if image_data:
            self.current_pixmap = QPixmap()
            self.current_pixmap.loadFromData(image_data)
            # Scale it down so it fits nicely above the chat
            scaled_pixmap = self.current_pixmap.scaledToHeight(300, Qt.TransformationMode.SmoothTransformation)
            self.cover_label.setPixmap(scaled_pixmap)
        else:
            self.cover_label.setText("Cover load failed.")

    def show_large_cover(self):
        if not hasattr(self, 'current_pixmap') or self.current_pixmap.isNull():
            return
            
        # Create a pop-up window for the full-size image
        dialog = QDialog(self)
        dialog.setWindowTitle(self.current_title or "Cover Image")
        layout = QVBoxLayout(dialog)
        
        large_label = QLabel()
        large_label.setPixmap(self.current_pixmap)
        large_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(large_label)
        dialog.exec()


# ==============================================================================
# COMIC CHAT TAB
# ==============================================================================
class ComicChatTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        
        self.header_label = QLabel("General Chat Mode")
        self.header_label.setStyleSheet("color: #8be9fd; font-weight: bold; font-size: 16px;")
        
        self.tts_status_label = QLabel("")
        self.tts_status_label.setStyleSheet("color: #f1fa8c; font-style: italic;")
        
        self.tts_toggle_btn = QPushButton("🔊 Voice: ON")
        self.tts_toggle_btn.setCheckable(True)
        self.tts_toggle_btn.setChecked(True)
        self.tts_toggle_btn.setFixedWidth(100)
        self.tts_toggle_btn.clicked.connect(self.toggle_voice)

        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.setFixedWidth(90)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setEnabled(False)

        self.stop_audio_btn = QPushButton("🛑 Stop")
        self.stop_audio_btn.setFixedWidth(80)
        self.stop_audio_btn.clicked.connect(self.stop_audio)
        self.stop_audio_btn.setEnabled(False)
        
        self.clear_btn = QPushButton("🗑️ Clear Chat")
        self.clear_btn.setFixedWidth(120)
        self.clear_btn.clicked.connect(self.clear_chat)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(self.header_label)
        header_layout.addStretch() 
        header_layout.addWidget(self.tts_status_label)
        header_layout.addWidget(self.tts_toggle_btn)
        header_layout.addWidget(self.pause_btn)
        header_layout.addWidget(self.stop_audio_btn)
        header_layout.addWidget(self.clear_btn)
        self.layout.addLayout(header_layout)
        
        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(False)
        self.layout.addWidget(self.chat_display)
        
        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ask the Interrogator about comics...")
        self.chat_input.returnPressed.connect(self.send_message)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(self.send_btn)
        self.layout.addLayout(input_layout)
        
        self.context_title = None
        self.context_summary = None
        self.history = []
        self.chat_thread = None
        self.tts_thread = None

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)
        self.audio_temp_file = os.path.join(CACHE_DIR, "chat_audio.mp3")

    def toggle_voice(self):
        if self.tts_toggle_btn.isChecked():
            self.tts_toggle_btn.setText("🔊 Voice: ON")
        else:
            self.tts_toggle_btn.setText("🔇 Voice: OFF")
            self.stop_audio()

    def stop_audio(self):
        self.player.stop()
        self.stop_audio_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸️ Pause")
        self.tts_status_label.setText("")

    def update_context(self, title, summary):
        self.context_title = title
        self.context_summary = summary
        self.header_label.setText(f"Discussing: {title}")

    def clear_chat(self):
        self.history.clear()
        self.chat_display.clear()
        self.stop_audio()

    def send_message(self):   
        user_text = self.chat_input.text().strip()
        if not user_text: return
        
        self.chat_input.clear()
        self.history.append({"role": "user", "content": user_text})
        self.append_chat_bubble("🦸 You", user_text, "#6272a4")
        
        self.send_btn.setEnabled(False)
        
        self.chat_thread = GeminiChatThread(self.context_summary, self.history.copy(), user_text)
        self.chat_thread.response_ready.connect(self.on_response)
        self.chat_thread.error_occurred.connect(self.on_error)
        self.chat_thread.start()

    def on_response(self, text):
        self.history.append({"role": "assistant", "content": text})
        self.append_chat_bubble("🤖 Interrogator", text, "#44475a")
        self.send_btn.setEnabled(True)

        if self.tts_toggle_btn.isChecked():
            self.tts_status_label.setText("🎙️ Generating audio...")
            self.stop_audio_btn.setEnabled(True)
            
            # Map the text name from Settings to the actual Microsoft Voice ID
            voice_map = {
                "Jenny (Standard US Female)": "en-US-JennyNeural",
                "Christopher (Deep US Male)": "en-US-ChristopherNeural", 
                "Aria (Clear US Female)": "en-US-AriaNeural",
                "Guy (Energetic US Male)": "en-US-GuyNeural",
                "Steffan (Pro US Male)": "en-US-SteffanNeural",
                "Ryan (British Male)": "en-GB-RyanNeural",
                "Sonia (British Female)": "en-GB-SoniaNeural",
                "Natasha (Australian Female)": "en-AU-NatashaNeural",
                "William (Australian Male)": "en-AU-WilliamNeural"
            }
            chosen_voice = voice_map.get(APP_SETTINGS["chat_voice"], "en-US-JennyNeural")
            
            self.tts_thread = TTSWorkerThread(text, chosen_voice)
            self.tts_thread.audio_ready.connect(self.on_audio_ready)
            self.tts_thread.start()

    def on_audio_ready(self, audio_data):

        # 1. Safely check if the player exists before trying to stop it
        if hasattr(self, 'player') and self.player is not None:
            self.player.stop()

        # 2. Save the raw bytes to a temporary chat audio file!
        temp_audio_path = os.path.join(tempfile.gettempdir(), "temp_chat_audio.mp3")
        with open(temp_audio_path, 'wb') as f:
            f.write(audio_data)

        # 3. Create the player and speaker (attached to 'self')
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0) 
        
        # 4. Plug the speaker into the player
        self.player.setAudioOutput(self.audio_output)
        
        # 5. Load the new temporary file and press play!
        self.player.setSource(QUrl.fromLocalFile(temp_audio_path))
        self.player.play()
        
        # 6. NEW: Wake the buttons back up so you can actually click them!
        if hasattr(self, 'pause_btn'): self.pause_btn.setEnabled(True)
        if hasattr(self, 'stop_audio_btn'): self.stop_audio_btn.setEnabled(True)

    # ⬅️ Look at this alignment! It must line up perfectly with 'def on_audio_ready'
    def toggle_pause(self):
        if hasattr(self, 'player') and self.player is not None:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()
                self.pause_btn.setText("▶️ Resume")
            else:
                self.player.play()
                self.pause_btn.setText("⏸️ Pause")
    def on_error(self, err):
        self.append_chat_bubble("⚠️ Error", err, "#ff5555")
        self.send_btn.setEnabled(True)

    def append_chat_bubble(self, sender, text, color):
        html_content = f"""
        <div style="background-color: {color}; padding: 10px; margin-bottom: 15px; border-radius: 8px; border-left: 4px solid #8be9fd;">
            <b style="color: #f8f8f2; font-size: 15px;">{sender}</b><br><br>
            <span style="color: #f8f8f2; font-size: 14px;">{markdown.markdown(text)}</span>
        </div><br>
        """
        self.chat_display.append(html_content)



# ==============================================================================
# NEW RELEASES TAB
# ==============================================================================
class NewReleasesTab(QWidget):
    open_url = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._current_week  = self._this_wednesday()
        self._fetch_thread  = None
        self._cover_thread  = None
        self._single_cover_threads = []  # one-off GCCoverThread for manual refresh
        self._check_thread  = None
        self._last_results  = {}
        self._cover_cache   = {}   # article_url -> bytes
        self._gc_status     = {}   # url -> article_url (from Check Releases)
        self._followed      = {}   # url -> {title}
        self._downloaded    = set()  # urls of successfully downloaded articles
        self._follow_collections = bool(APP_SETTINGS.get("follow_collections", False))
        self._auto_followed_urls = set()  # urls added by the bulk "follow collections" toggle
        self._active_groups = {}
        self._render_groups = {}
        self._copied_page_links = set()
        self._hoster_downloaded = set()
        self._cover_tab_inflight = None  # category currently being covered

        # Persist copy / hoster indicators (used for green check on titles).
        # Use absolute paths so files are found regardless of cwd on restart.
        _nr_dir = os.path.dirname(os.path.abspath(__file__))
        self._copied_file = os.path.join(_nr_dir, "copied_page_links.json")
        self._hoster_file = os.path.join(_nr_dir, "hoster_downloaded.json")
        self._cleared_watch_file = os.path.join(_nr_dir, "cleared_from_watched_urls.json")
        self._cleared_watch_urls = set()
        _n = self._norm_gc_url
        try:
            if os.path.exists(self._copied_file):
                with open(self._copied_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        self._copied_page_links = {_n(str(x)) for x in raw if _n(str(x))}
        except Exception:
            self._copied_page_links = set()
        try:
            if os.path.exists(self._hoster_file):
                with open(self._hoster_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        self._hoster_downloaded = {_n(str(x)) for x in raw if _n(str(x))}
        except Exception:
            self._hoster_downloaded = set()
        try:
            if os.path.exists(self._cleared_watch_file):
                with open(self._cleared_watch_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        self._cleared_watch_urls = {_n(str(x)) for x in raw if _n(str(x))}
        except Exception:
            self._cleared_watch_urls = set()

        try:
            if os.path.exists(FOLLOWED_SERIES_FILE):
                with open(FOLLOWED_SERIES_FILE) as f:
                    saved = json.load(f)
                    norm = {}
                    if isinstance(saved, dict):
                        for k, v in saved.items():
                            if isinstance(v, dict):
                                norm[k] = {
                                    "title": v.get("title", "") or str(k),
                                    "date": v.get("date", "") or "",
                                }
                            else:
                                norm[k] = {"title": str(v) if v else str(k), "date": ""}
                    self._followed = norm
        except Exception:
            self._followed = {}

        # Load downloaded set
        self._dl_file = os.path.join(_nr_dir, "downloaded_comics.json")
        try:
            if os.path.exists(self._dl_file):
                with open(self._dl_file) as f:
                    raw = json.load(f)
                self._downloaded = {_n(str(x)) for x in (raw or []) if _n(str(x))}
            else:
                self._downloaded = set()
        except Exception:
            self._downloaded = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        hdr = QLabel("New Releases")
        hdr.setStyleSheet("color:#ffb86c; font-weight:bold; font-size:16px;")
        layout.addWidget(hdr)

        # Week nav row
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Prev Week")
        self.prev_btn.setStyleSheet(
            "background:#44475a; color:#f8f8f2; padding:6px 14px; border-radius:4px; font-weight:bold;")
        self.prev_btn.clicked.connect(self._prev_week)

        self.week_lbl = QLabel()
        self.week_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_lbl.setStyleSheet("color:#8be9fd; font-size:14px; font-weight:bold;")

        self.next_btn = QPushButton("Next Week ▶")
        self.next_btn.setStyleSheet(
            "background:#44475a; color:#f8f8f2; padding:6px 14px; border-radius:4px; font-weight:bold;")
        self.next_btn.clicked.connect(self._next_week)

        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setStyleSheet(
            "background:#6272a4; color:#f8f8f2; padding:6px 10px; border-radius:4px;")
        self.refresh_btn.clicked.connect(self._load_week)

        nav.addWidget(self.prev_btn)
        nav.addStretch()
        nav.addWidget(self.week_lbl)
        nav.addStretch()
        nav.addWidget(self.next_btn)
        nav.addWidget(self.refresh_btn)
        layout.addLayout(nav)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet("color:#6272a4; font-size:11px;")
        layout.addWidget(self.count_lbl)

        # Collection follow control row (global for all tabs)
        tabs_header = QHBoxLayout()
        tabs_header.setContentsMargins(0, 0, 0, 0)
        tabs_header.setSpacing(8)

        tabs_title = QLabel("Publishers")
        tabs_title.setStyleSheet("color:#6272a4; font-size:11px; font-weight:bold;")
        tabs_header.addWidget(tabs_title)
        tabs_header.addStretch()

        self.watched_filter = QComboBox()
        self.watched_filter.addItems(["Watched: All", "Watched: Issues only", "Watched: Collections only"])
        self.watched_filter.setCurrentIndex(0)
        self.watched_filter.setStyleSheet(
            "QComboBox { background:#21222c; color:#f8f8f2; border:1px solid #44475a; padding:4px 8px; }"
        )
        self.watched_filter.currentIndexChanged.connect(self._on_watched_filter_changed)
        tabs_header.addWidget(self.watched_filter)

        self.clear_downloaded_btn = QPushButton("Clear Downloaded")
        self.clear_downloaded_btn.setStyleSheet(
            "background:#44475a; color:#f8f8f2; padding:4px 10px; border-radius:4px; font-size:11px;"
        )
        self.clear_downloaded_btn.clicked.connect(self._clear_downloaded_from_followed)
        tabs_header.addWidget(self.clear_downloaded_btn)

        follow_col_wrap = QWidget()
        follow_col_v = QVBoxLayout(follow_col_wrap)
        follow_col_v.setContentsMargins(0, 0, 0, 0)
        follow_col_v.setSpacing(2)
        self.follow_col_cb = QCheckBox("📚 Follow all Collections (omnibus, TPB, vol., etc.)")
        self.follow_col_cb.setChecked(self._follow_collections)
        self.follow_col_cb.setStyleSheet(
            "color:#bd93f9; font-size:11px; font-weight:bold; padding:4px;")
        self.follow_col_cb.toggled.connect(self._on_follow_collections_toggled)
        follow_col_v.addWidget(self.follow_col_cb)
        copy_link_hint = QLabel("Right click to copy link address")
        copy_link_hint.setStyleSheet("color:#6272a4; font-size:9px; background:transparent;")
        copy_link_hint.setWordWrap(True)
        follow_col_v.addWidget(copy_link_hint)
        tabs_header.addWidget(follow_col_wrap)
        layout.addLayout(tabs_header)

        # Three publisher sub-tabs
        self.pub_tabs = QTabWidget()
        self.pub_tabs.setStyleSheet("""
            QTabBar::tab { background:#21222c; color:#f8f8f2; padding:6px 18px; }
        """)
        self.dc_scroll,  self.dc_layout  = self._make_scroll()
        self.mv_scroll,  self.mv_layout  = self._make_scroll()
        self.oth_scroll, self.oth_layout = self._make_scroll()
        self.col_scroll, self.col_layout = self._make_scroll()
        self.wt_scroll,  self.wt_layout  = self._make_scroll()
        self.pub_tabs.addTab(self.dc_scroll,  "DC Comics")
        self.pub_tabs.addTab(self.mv_scroll,  "Marvel")

        self.pub_tabs.addTab(self.oth_scroll, "Others")
        self.pub_tabs.addTab(self.col_scroll, "Collections")
        self.pub_tabs.addTab(self.wt_scroll,  "Watched")
        self.pub_tabs.currentChanged.connect(self._on_pub_tab_changed)
        layout.addWidget(self.pub_tabs, stretch=1)

        self.status_lbl = QLabel("Loading…")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color:#6272a4; font-size:13px;")
        layout.addWidget(self.status_lbl)

        self._update_week_label()
        self._load_week()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _make_scroll(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        lay.addStretch()
        scroll.setWidget(container)
        return scroll, lay

    @staticmethod
    def _norm_gc_url(u: str) -> str:
        """Normalize GetComics URL for consistent comparison (feed uses getcomics.org)."""
        u = (u or "").strip().rstrip("/")
        if not u:
            return ""
        lower = u.lower()
        if "getcomics.info" in lower:
            u = re.sub(r"getcomics\.info", "getcomics.org", u, flags=re.IGNORECASE)
        return u

    def _is_url_completed(self, url: str) -> bool:
        """True if this URL is in downloaded, copied, or hoster sets (shows check in all sections)."""
        if not url:
            return False
        un = self._norm_gc_url(url)
        raw = (url or "").strip().rstrip("/")
        # Check normalized, raw, and domain swap (getcomics.org <-> getcomics.info)
        variants = {un, raw}
        if un:
            variants.add(re.sub(r"getcomics\.org", "getcomics.info", un, flags=re.IGNORECASE))
            variants.add(re.sub(r"getcomics\.info", "getcomics.org", un, flags=re.IGNORECASE))
        for s in (self._downloaded, self._copied_page_links, self._hoster_downloaded):
            if any(v and v in s for v in variants):
                return True
        return False

    def _save_cleared_watch_urls(self):
        try:
            with open(self._cleared_watch_file, "w", encoding="utf-8") as f:
                json.dump(sorted(self._cleared_watch_urls), f, indent=2)
        except Exception as _e:
            log.warning("Could not save cleared watch list: %s", _e)

    def _nr_information(self, title: str, text: str):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(text)
        msg.setStyleSheet(DRACULA_MSGBOX_QSS)
        msg.exec()

    def _watched_entries_filtered(self, groups):
        """Watched list entries as shown under the current filter (matches Watched tab)."""
        groups = groups or {}
        dc_issues = [e for e in groups.get("dc", []) if not self._is_collection(e.get("title", ""))]
        mv_issues = [e for e in groups.get("marvel", []) if not self._is_collection(e.get("title", ""))]
        oth_issues = [e for e in groups.get("other", []) if not self._is_collection(e.get("title", ""))]
        col_entries = [
            e for e in (groups.get("dc", []) + groups.get("marvel", []) + groups.get("other", []))
            if self._is_collection(e.get("title", ""))
        ]
        week_order = dc_issues + mv_issues + oth_issues + col_entries
        week_urls = {e.get("url", "") for e in week_order if e.get("url", "")}

        _n = self._norm_gc_url
        watched_entries = []
        for e in week_order:
            u = e.get("url", "")
            if u and u in self._followed and _n(u) not in self._cleared_watch_urls:
                watched_entries.append(e)
        for u, meta in self._followed.items():
            if not isinstance(u, str) or not u.startswith("http"):
                continue
            if u in week_urls or _n(u) in self._cleared_watch_urls:
                continue
            md = meta if isinstance(meta, dict) else {"title": str(meta), "date": ""}
            watched_entries.append({
                "title": md.get("title", u),
                "url": u,
                "date": md.get("date", ""),
                "_outside_week": True,
            })

        def _watched_sort_key(e):
            ds = str(e.get("date", "") or "").strip()
            try:
                d = datetime.datetime.strptime(ds, "%B %d, %Y").date()
                return (0, -d.toordinal(), str(e.get("title", "")).lower())
            except Exception:
                return (1, 0, str(e.get("title", "")).lower())

        watched_entries.sort(key=_watched_sort_key)
        watched_mode = self.watched_filter.currentIndex() if hasattr(self, "watched_filter") else 0
        if watched_mode == 1:
            watched_entries = [e for e in watched_entries if not self._is_collection(e.get("title", ""))]
        elif watched_mode == 2:
            watched_entries = [e for e in watched_entries if self._is_collection(e.get("title", ""))]
        return watched_entries

    def _cat_for_tab_index(self, idx: int) -> str:
        # Keep in sync with tab order.
        if idx == 0:
            return "dc"
        if idx == 1:
            return "marvel"
        if idx == 2:
            return "other"
        if idx == 3:
            return "collections"
        return "watched"

    def _on_pub_tab_changed(self, idx: int):
        # Priority-loading: switch cover fetching to match the selected tab.
        self._start_cover_loading_for_tab(idx)

    def _on_watched_filter_changed(self, _idx: int):
        if self._last_results:
            self._render(self._last_results)
            if self._cat_for_tab_index(self.pub_tabs.currentIndex()) == "watched":
                self._start_cover_loading_for_tab(self.pub_tabs.currentIndex())

    def _clear_downloaded_from_followed(self):
        if not self._followed:
            return
        _n = self._norm_gc_url
        to_remove = [
            u for u in self._followed.keys()
            if _n(u) in self._downloaded
            or _n(u) in self._copied_page_links
            or _n(u) in self._hoster_downloaded
        ]
        if not to_remove:
            self._nr_information(
                "Clear Downloaded",
                "No completed items in Watched (download, copy link, or hoster).",
            )
            return
        for u in to_remove:
            self._followed.pop(u, None)
            self._auto_followed_urls.discard(u)
            self._cleared_watch_urls.add(_n(u))
            # Keep _downloaded, _copied_page_links, _hoster_downloaded intact so check marks
            # remain in DC/Marvel/Others sections (only remove from Watched list).
        self._save_followed()
        self._save_cleared_watch_urls()
        if self._last_results:
            self._render(self._last_results)
        self._update_watched_badge()

    def _watch_key(self, title: str) -> str:
        """Normalize a release title to a stable series key for follow carry-over."""
        t = html.unescape(str(title or "")).lower()
        t = re.sub(r'\(\d{4}\)', '', t)                     # drop trailing year
        t = re.sub(r'#\s*\d+(\.\d+)?\b', '', t)             # drop issue number
        t = re.sub(r'\b(issue|iss)\s*\d+\b', '', t)         # alternate issue labels
        t = re.sub(r'[\-–—_:]+', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def _start_cover_loading_for_tab(self, idx: int):
        cat = self._cat_for_tab_index(idx)
        if not self._render_groups or cat not in self._render_groups:
            return

        entries = self._render_groups.get(cat, [])
        if not entries:
            return

        if self._cover_thread and self._cover_thread.isRunning():
            # If user switches tabs mid-load, restart fetching for the new category.
            self._cover_thread.stop()
            self._cover_thread.quit()
            self._cover_thread.wait(2000)

        # Load only covers we don't already have cached.
        to_fetch = [
            e for e in entries
            if e.get("url")
            and not e.get("_no_cover")
            and e.get("url") not in self._cover_cache
        ]
        # Watched can be large; fetch only newest visible slice to prevent hangs.
        if cat == "watched" and len(to_fetch) > 30:
            to_fetch = to_fetch[:30]
        if not to_fetch:
            return

        self._cover_thread = GCCoverThread(to_fetch)
        self._cover_thread.cover_ready.connect(self._on_cover)
        self._cover_thread.start()

        self._cover_tab_inflight = cat

    def _update_publisher_tab_badges(self, groups):
        # Put counts into the labels (e.g. "DC Comics (12)")
        dc_n = sum(1 for e in groups.get("dc", []) if not self._is_collection(e.get("title", "")))
        mv_n = sum(1 for e in groups.get("marvel", []) if not self._is_collection(e.get("title", "")))
        oth_n = sum(1 for e in groups.get("other", []) if not self._is_collection(e.get("title", "")))
        col_n = sum(
            1 for e in (groups.get("dc", []) + groups.get("marvel", []) + groups.get("other", []))
            if self._is_collection(e.get("title", ""))
        )

        self.pub_tabs.setTabText(0, f"DC Comics ({dc_n})")
        self.pub_tabs.setTabText(1, f"Marvel ({mv_n})")
        self.pub_tabs.setTabText(2, f"Others ({oth_n})")
        self.pub_tabs.setTabText(3, f"Collections ({col_n})")

        # Watched tab: same count as rows under the current Watched filter.
        watched_n = len(self._watched_entries_filtered(groups))
        self.pub_tabs.setTabText(4, f"Watched ({watched_n})")

    def _update_watched_badge(self):
        groups = self._active_groups or self._last_results or {}
        if groups:
            # This recomputes all three publisher counts too.
            self._update_publisher_tab_badges(groups)

    @staticmethod
    def _this_wednesday():
        today = datetime.date.today()
        return today - datetime.timedelta(days=(today.weekday() - 2) % 7)

    def _update_week_label(self):
        end = self._current_week + datetime.timedelta(days=6)
        s = self._current_week.strftime("%b ") + str(self._current_week.day)
        e = end.strftime("%b ") + str(end.day) + end.strftime(", %Y")
        self.week_lbl.setText(f"Week of {s} – {e}")
        self.next_btn.setEnabled(
            self._current_week + datetime.timedelta(days=7) <= datetime.date.today())

    def _prev_week(self):
        self._current_week -= datetime.timedelta(days=7)
        self._gc_status.clear()
        self._update_week_label()
        self._load_week()

    def _next_week(self):
        self._current_week += datetime.timedelta(days=7)
        self._gc_status.clear()
        self._update_week_label()
        self._load_week()

    def _save_followed(self):
        try:
            with open(FOLLOWED_SERIES_FILE, "w") as f:
                json.dump(self._followed, f, indent=2)
        except Exception as _e:
            log.warning("Could not save followed: %s", _e)

    def _merge_follow_entry(self, url: str, title: str, post_date: str = ""):
        """Store title + GetComics post date so Watched still shows them off-week."""
        if not url:
            return
        old = self._followed.get(url)
        if isinstance(old, dict):
            prev = dict(old)
        else:
            prev = {"title": str(old) if old else "", "date": ""}
        new_title = (title or "").strip() or (prev.get("title") or "").strip()
        new_date = (post_date or "").strip() or (prev.get("date") or "").strip()
        self._followed[url] = {"title": new_title, "date": new_date}

    def _on_follow_collections_toggled(self, checked):
        self._follow_collections = checked
        APP_SETTINGS["follow_collections"] = bool(checked)
        try:
            with open("settings.json", "w") as f:
                json.dump(APP_SETTINGS, f)
        except Exception:
            pass
        if checked:
            if self._last_results:
                _n = self._norm_gc_url
                for entries in self._last_results.values():
                    for entry in entries:
                        if not self._is_collection(entry.get("title", "")):
                            continue
                        u = entry.get("url", "")
                        if u and u not in self._followed and _n(u) not in self._cleared_watch_urls:
                            self._merge_follow_entry(
                                u, entry.get("title", ""), entry.get("date", ""))
                            self._auto_followed_urls.add(u)
                self._save_followed()
                self._render(self._last_results)
        else:
            # When turning off: unfollow currently followed collection entries,
            # but keep regular issue follows.
            to_remove = []
            for u, meta in self._followed.items():
                t = (meta or {}).get("title", "")
                if t and self._is_collection(t):
                    to_remove.append(u)
            for u in to_remove:
                self._followed.pop(u, None)
                self._auto_followed_urls.discard(u)
            self._save_followed()
            if self._last_results:
                self._render(self._last_results)

    def _save_downloaded(self):
        try:
            with open(self._dl_file, "w") as f:
                json.dump(list(self._downloaded), f)
        except Exception as _e:
            log.warning("Could not save downloaded list: %s", _e)

    def _save_json_set(self, filename: str, s: set):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(sorted(s), f, indent=2)
        except Exception as _e:
            log.warning("Could not save %s: %s", filename, _e)

    def _title_html(self, url: str, base_title: str) -> str:
        """Return HTML for title label with green checks (shows in all sections: DC, Marvel, Others, Collections, Watched)."""
        t = html.escape(base_title or "")
        if self._is_url_completed(url):
            return "<span style='color:#50fa7b;font-weight:bold;'>✓</span> " + t
        return t

    def _refresh_title_check(self, url: str):
        for lbl in self.findChildren(QLabel):
            if lbl.property("title_label_for") != url:
                continue
            base_title = lbl.property("title_base") or ""
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setText(self._title_html(url, base_title))

    def _copy_page_link(self, url: str):
        """Copy GetComics/redirect article URL so you can paste into jdownloader."""
        u = (url or "").strip()
        if not u:
            return
        QApplication.clipboard().setText(u)
        self._copied_page_links.add(self._norm_gc_url(u))
        self._save_json_set(self._copied_file, self._copied_page_links)
        self._refresh_title_check(url)

    def _show_copy_link_menu(self, pos, url: str):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #282a36; color: #f8f8f2; border: 1px solid #44475a; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #44475a; }
        """)
        copy_action = menu.addAction("Copy page link")
        btn = self.sender()
        if btn is not None and hasattr(btn, "mapToGlobal"):
            gpos = btn.mapToGlobal(pos)
        else:
            gpos = self.mapToGlobal(pos)
        action = menu.exec(gpos)
        if action == copy_action:
            self._copy_page_link(url)

    def _show_cover_context_menu(self, pos, article_url: str):
        if not (article_url or "").strip():
            return
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #282a36; color: #f8f8f2; border: 1px solid #44475a; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #44475a; }
        """)
        refresh_act = menu.addAction("Refresh cover")
        btn = self.sender()
        if btn is not None and hasattr(btn, "mapToGlobal"):
            gpos = btn.mapToGlobal(pos)
        else:
            gpos = self.mapToGlobal(pos)
        act = menu.exec(gpos)
        if act == refresh_act:
            self._refresh_gc_cover(article_url.strip())

    def _refresh_gc_cover(self, article_url: str):
        """Re-fetch og:image for one card (longer timeout, clears cache first)."""
        u = (article_url or "").strip()
        if not u:
            return
        self._cover_cache.pop(u, None)
        gc_new_releases_uncache_thumb(u)
        for lbl in self.findChildren(QLabel):
            if lbl.property("gc_url") == u:
                lbl.clear()
                lbl.setText("Refreshing…")
        thr = GCCoverThread(
            [{"url": u, "title": "", "date": ""}],
            request_timeout=15,
            delay_between=0,
        )
        thr.cover_ready.connect(self._on_refreshed_single_cover)
        thr.finished.connect(thr.deleteLater)

        def _pop():
            try:
                self._single_cover_threads.remove(thr)
            except ValueError:
                pass
        thr.finished.connect(_pop)
        self._single_cover_threads.append(thr)
        thr.start()

    def _on_refreshed_single_cover(self, article_url: str, data: bytes):
        self._cover_cache[article_url] = data
        self._on_cover(article_url, data)
        if not data:
            for lbl in self.findChildren(QLabel):
                if lbl.property("gc_url") == article_url:
                    lbl.setText("No cover")

    def mark_downloaded(self, url: str, via_hoster: bool = False):
        """Called by ComicBrowser when a download completes for a GC article URL."""
        u = (url or "").strip()
        if not u:
            return
        un = self._norm_gc_url(u)
        self._downloaded.add(un)
        self._save_downloaded()
        if via_hoster:
            self._hoster_downloaded.add(un)
            self._save_json_set(self._hoster_file, self._hoster_downloaded)
        self._refresh_title_check(u)
        self._update_watched_badge()

    def hideEvent(self, event):
        for t in [self._fetch_thread, self._cover_thread, self._check_thread]:
            if t and t.isRunning():
                if t == self._cover_thread and hasattr(t, "stop"):
                    t.stop()
                t.quit()
                t.wait(2000)
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # Covers were cached while minimized; repaint labels now.
        self._refresh_covers_from_cache()
        # Refresh badge counts when tab becomes visible (fixes counts not showing until layout triggers).
        self._update_watched_badge()

    def _refresh_covers_from_cache(self):
        for lbl in self.findChildren(QLabel):
            u = lbl.property("gc_url")
            if not u:
                continue
            data = self._cover_cache.get(u)
            if not data:
                continue
            pix = QPixmap()
            if pix.loadFromData(data) and not pix.isNull():
                lbl.setPixmap(pix.scaled(
                    130, 195,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                lbl.setText("")

    def _clear_all(self):
        if self._cover_thread and self._cover_thread.isRunning():
            self._cover_thread.stop()
            self._cover_thread.quit()
            self._cover_thread.wait(2000)
        for lay in (self.dc_layout, self.mv_layout, self.oth_layout, self.col_layout, self.wt_layout):
            while lay.count() > 1:
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

    def _load_week(self):
        self._clear_all()
        self.status_lbl.setText("🔍 Fetching from GetComics…")
        self.count_lbl.setText("")
        self.refresh_btn.setEnabled(False)
        if self._fetch_thread and self._fetch_thread.isRunning():
            self._fetch_thread.quit()
            self._fetch_thread.wait()
        self._fetch_thread = GCSitemapThread(self._current_week)
        self._fetch_thread.results_ready.connect(self._on_results)
        self._fetch_thread.error_occurred.connect(self._on_error)
        self._fetch_thread.start()

    def _on_error(self, msg):
        self.status_lbl.setText(f"⚠️ {msg}")
        self.refresh_btn.setEnabled(True)

    def _on_results(self, groups):
        self.refresh_btn.setEnabled(True)
        total = sum(len(v) for v in groups.values())
        if not total:
            self.status_lbl.setText("No releases found for this week on GetComics.")
            return
        self._last_results = groups
        self._active_groups = groups
        _n = self._norm_gc_url

        # Carry follows forward to newly released issues/collections that match
        # previously followed series keys.
        followed_keys = set()
        for meta in self._followed.values():
            if isinstance(meta, dict):
                mk = self._watch_key(meta.get("title", ""))
                if mk:
                    followed_keys.add(mk)
        if followed_keys:
            for entries in groups.values():
                for entry in entries:
                    u = entry.get("url", "")
                    if not u or u in self._followed or _n(u) in self._cleared_watch_urls:
                        continue
                    ek = self._watch_key(entry.get("title", ""))
                    if ek and ek in followed_keys:
                        self._merge_follow_entry(
                            u, entry.get("title", ""), entry.get("date", ""))
            self._save_followed()
        self.count_lbl.setText(
            f"({total}) releases  •  DC ({len(groups['dc'])})  "
            f"Marvel ({len(groups['marvel'])})  Others ({len(groups['other'])})")
        self.status_lbl.setText("")
        # If bulk-follow is enabled, add all *collection-type* releases that
        # are visible right now (but keep manual follows intact).
        if self._follow_collections:
            for entries in groups.values():
                for entry in entries:
                    if not self._is_collection(entry.get("title", "")):
                        continue
                    u = entry.get("url", "")
                    if u and u not in self._followed and _n(u) not in self._cleared_watch_urls:
                        self._merge_follow_entry(
                            u, entry.get("title", ""), entry.get("date", ""))
                        self._auto_followed_urls.add(u)
            self._save_followed()

        self._render(groups)
        # Only fetch covers for the active tab so switching tabs "interrupts" work.
        self._start_cover_loading_for_tab(self.pub_tabs.currentIndex())

    def _on_cover(self, article_url, data):
        self._cover_cache[article_url] = data
        # If app/tab is hidden or minimized, avoid expensive widget scanning.
        if not self.isVisible():
            return
        for lbl in self.findChildren(QLabel):
            if lbl.property("gc_url") == article_url and data:
                pix = QPixmap()
                if pix.loadFromData(data) and not pix.isNull():
                    lbl.setPixmap(pix.scaled(
                        130, 195,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation))
                    lbl.setText("")

    def _render(self, groups):
        self._clear_all()
        colours = {
            "dc": "#0476D0",
            "marvel": "#ff0000",
            "other": "#44475a",
            "collections": "#ffb86c",
            "watched": "#bd93f9",
        }
        layouts = {
            "dc": self.dc_layout,
            "marvel": self.mv_layout,
            "other": self.oth_layout,
            "collections": self.col_layout,
            "watched": self.wt_layout,
        }

        # Split collection posts out of normal publisher lists so those tabs
        # show issue-like posts only.
        dc_issues = [e for e in groups.get("dc", []) if not self._is_collection(e.get("title", ""))]
        mv_issues = [e for e in groups.get("marvel", []) if not self._is_collection(e.get("title", ""))]
        oth_issues = [e for e in groups.get("other", []) if not self._is_collection(e.get("title", ""))]
        col_entries = [
            e for e in (groups.get("dc", []) + groups.get("marvel", []) + groups.get("other", []))
            if self._is_collection(e.get("title", ""))
        ]

        current_by_url = {}
        for entries in (dc_issues, mv_issues, oth_issues, col_entries):
            for e in entries:
                u = e.get("url", "")
                if u:
                    current_by_url[u] = e

        # Build watched from current-week followed entries + older followed links.
        week_order = dc_issues + mv_issues + oth_issues + col_entries
        week_urls = {e.get("url", "") for e in week_order if e.get("url", "")}

        # Refresh stored title/date when a followed URL appears in this week's feed.
        _follow_dirty = False
        for e in week_order:
            u = e.get("url", "")
            if not u or u not in self._followed:
                continue
            old = self._followed[u]
            if not isinstance(old, dict):
                old = {"title": str(old), "date": ""}
            newd = dict(old)
            if e.get("title"):
                newd["title"] = e["title"]
            if e.get("date"):
                newd["date"] = e["date"]
            if newd != old:
                self._followed[u] = newd
                _follow_dirty = True
        if _follow_dirty:
            self._save_followed()

        watched_entries = self._watched_entries_filtered(groups)

        render_groups = {
            "dc": dc_issues,
            "marvel": mv_issues,
            "other": oth_issues,
            "collections": col_entries,
            "watched": watched_entries,
        }
        # Used by the cover loader so we can priority-load the active tab.
        self._render_groups = render_groups

        for cat, entries in render_groups.items():
            lay = layouts[cat]
            border = colours[cat]
            COLS = 3
            for row_idx in range(0, len(entries), COLS):
                group = entries[row_idx:row_idx + COLS]
                row_w = QWidget()
                row_w.setStyleSheet("background:transparent;")
                row_l = QHBoxLayout(row_w)
                row_l.setContentsMargins(0, 0, 0, 0)
                row_l.setSpacing(8)
                for entry in group:
                    card = self._make_card(entry, border)
                    row_l.addWidget(card, stretch=1)
                for _ in range(COLS - len(group)):
                    row_l.addStretch(1)
                lay.insertWidget(lay.count() - 1, row_w)

        QTimer.singleShot(0, lambda g=groups: self._update_publisher_tab_badges(g))

    def _is_collection(self, title: str) -> bool:
        t = title.lower()
        # Explicit collection imprint
        if "dc finest" in t:
            return True
        # If the title clearly references a single issue number, prefer issue classification.
        # This avoids false positives like:
        # - Batman – Superman – World's Finest #49
        # - The Walking Dead Deluxe #133
        if re.search(r'#\s*\d+(\.\d+)?\b', t):
            return False
        return any(kw in t for kw in (
            # NOTE: Intentionally exclude "absolute". "Absolute" is a DC/brand
            # label for some issues/series and should not be treated as a
            # collected-volume type by the bulk follow toggle.
            "omnibus", "compendium", "tpb", "trade paperback",
            "collected", "collection", "vol.", "volume", "book ",
            "treasury", "epic collection", "masterworks",
        ))

    def _make_card(self, entry, border_colour):
        title = html.unescape(entry.get("title", ""))
        url = entry.get("url", "")
        date = entry.get("date", "")
        is_col = self._is_collection(title)
        is_followed = url in self._followed
        is_downloaded = url in self._downloaded
        COVER_W, COVER_H = 130, 195
        card = QWidget()
        card.setObjectName("releaseCard")
        card.setStyleSheet("""
            QWidget#releaseCard       { background:#282a36; border-radius:6px; }
            QWidget#releaseCard:hover { background:#2d2f3e; }
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 8, 8, 8)
        cl.setSpacing(4)
        cover_frame = QWidget()
        cover_frame.setFixedSize(COVER_W + 4, COVER_H + 4)
        cover_frame.setStyleSheet(f"background:{border_colour}; border-radius:5px;")
        frame_l = QVBoxLayout(cover_frame)
        frame_l.setContentsMargins(2, 2, 2, 2)
        cover_lbl = QLabel()
        cover_lbl.setFixedSize(COVER_W, COVER_H)
        cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_lbl.setStyleSheet(
            "background:#21222c; border-radius:3px; color:#6272a4; font-size:10px;")
        cover_lbl.setText("Loading…")
        cover_lbl.setProperty("gc_url", url)
        cover_lbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        cover_lbl.customContextMenuRequested.connect(
            lambda pos, u=url: self._show_cover_context_menu(pos, u)
        )
        frame_l.addWidget(cover_lbl)
        cl.addWidget(cover_frame, alignment=Qt.AlignmentFlag.AlignHCenter)
        # Hot path: show disk thumbnail immediately (same cache as GCCoverThread).
        if url and url not in self._cover_cache:
            tp = gc_new_releases_thumb_path(url)
            if os.path.isfile(tp):
                try:
                    with open(tp, "rb") as tf:
                        disk_b = tf.read()
                    if disk_b:
                        self._cover_cache[url] = disk_b
                except OSError:
                    pass
        if url in self._cover_cache and self._cover_cache[url]:
            pix = QPixmap()
            if pix.loadFromData(self._cover_cache[url]) and not pix.isNull():
                cover_lbl.setPixmap(pix.scaled(
                    COVER_W, COVER_H,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                cover_lbl.setText("")
        cl.addSpacing(12)
        tl = QLabel()
        tl.setStyleSheet(
            "color:#f8f8f2; font-weight:bold; font-size:11px; "
            "background:transparent;")
        tl.setTextFormat(Qt.TextFormat.RichText)
        tl.setText(self._title_html(url, title))
        tl.setWordWrap(True)
        tl.setMaximumWidth(COVER_W + 20)
        cl.addWidget(tl)
        tl.setProperty("title_label_for", url)
        tl.setProperty("title_base", title)
        if date:
            dl = QLabel(date)
            dl.setStyleSheet("color:#6272a4; font-size:9px; background:transparent;")
            cl.addWidget(dl)
        elif entry.get("_outside_week"):
            dl = QLabel("Not in selected week")
            dl.setStyleSheet(
                "color:#6272a4; font-size:9px; background:transparent; font-style:italic;")
            cl.addWidget(dl)
        cl.addStretch()
        follow_cb = QCheckBox("Follow")
        # Only show "followed" if it's actually in the watched list.
        # Bulk-follow works by populating _followed, not by overriding UI state.
        follow_cb.setChecked(is_followed)
        follow_cb.setStyleSheet("color:#ffb86c; font-size:9px; background:transparent;")
        def _toggle(checked, u=url, t=title):
            if checked:
                self._merge_follow_entry(u, t, date)
                # If user manually re-followed after a bulk auto-unfollow, it
                # should not be treated as "auto-followed".
                self._auto_followed_urls.discard(u)
                self._cleared_watch_urls.discard(self._norm_gc_url(u))
                self._save_cleared_watch_urls()
            else:
                self._followed.pop(u, None)
                self._auto_followed_urls.discard(u)
            self._save_followed()
            if self._last_results:
                self._render(self._last_results)
        follow_cb.toggled.connect(_toggle)
        cl.addWidget(follow_cb)
        dl_btn = QPushButton("⬇ Download")
        dl_btn.setStyleSheet(
            "background:#50fa7b; color:#282a36; font-weight:bold; "
            "padding:4px 0; border-radius:4px; font-size:10px;")
        dl_btn.clicked.connect(lambda _, u=url: self.open_url.emit(u))
        # Right-click "Copy page link"
        dl_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        dl_btn.customContextMenuRequested.connect(
            lambda pos, u=url: self._show_copy_link_menu(pos, u)
        )
        cl.addWidget(dl_btn)
        return card


# ==============================================================================
# SETTINGS TAB
# ==============================================================================
class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # --- API Keys ---
        self.layout.addWidget(QLabel("🔑 API Keys (Requires App Restart to Apply)"))
        
        cv_layout = QHBoxLayout()
        cv_layout.addWidget(QLabel("Comic Vine Key:"))
        self.cv_input = QLineEdit(APP_SETTINGS["cv_key"])
        self.cv_input.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        cv_layout.addWidget(self.cv_input)
        self.layout.addLayout(cv_layout)
        
        gem_layout = QHBoxLayout()
        gem_layout.addWidget(QLabel("Gemini API Key: "))
        self.gem_input = QLineEdit(APP_SETTINGS["gemini_key"])
        self.gem_input.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        gem_layout.addWidget(self.gem_input)
        self.layout.addLayout(gem_layout)

        self.layout.addSpacing(20)
        
        # --- External Reader ---
        self.layout.addWidget(QLabel("📖 External Comic Reader"))
        reader_layout = QHBoxLayout()
        self.reader_input = QLineEdit(APP_SETTINGS["reader_path"])
        self.reader_btn = QPushButton("Browse...")
        self.reader_btn.clicked.connect(self.browse_reader)
        reader_layout.addWidget(self.reader_input)
        reader_layout.addWidget(self.reader_btn)
        self.layout.addLayout(reader_layout)
        
        self.layout.addSpacing(20)
        
        # --- Chat Voice Settings ---
        self.layout.addWidget(QLabel("🎙️ Comic Chat Voice Settings"))
        self.voice_combo = QComboBox()
        self.voices = [
            "Christopher (Deep US Male)", "Aria (Clear US Female)",
            "Guy (Energetic US Male)", "Jenny (Standard US Female)",
            "Steffan (Pro US Male)", "Ryan (British Male)",
            "Sonia (British Female)", "Natasha (Australian Female)",
            "William (Australian Male)"
        ]
        self.voice_combo.addItems(self.voices)
        self.voice_combo.setCurrentText(APP_SETTINGS["chat_voice"])
        self.layout.addWidget(self.voice_combo)
        
        speed_layout = QHBoxLayout()
        speed_val = APP_SETTINGS["chat_speed"]
        self.speed_label = QLabel(f"Speed: {speed_val / 10.0}x")
        self.speed_label.setFixedWidth(65)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(5, 20) 
        self.speed_slider.setValue(speed_val)    
        self.speed_slider.valueChanged.connect(self.change_speed)
        speed_layout.addWidget(self.speed_label)
        speed_layout.addWidget(self.speed_slider)
        self.layout.addLayout(speed_layout)
        
        self.layout.addSpacing(30)
        
        # --- Save Button ---
        self.save_btn = QPushButton("💾 Save Settings")
        self.save_btn.setStyleSheet("background-color: #50fa7b; color: #282a36; font-weight: bold; padding: 10px;")
        self.save_btn.clicked.connect(self.save_settings)
        self.layout.addWidget(self.save_btn)

    def change_speed(self, value):
        self.speed_label.setText(f"Speed: {value / 10.0}x")

    def browse_reader(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Reader Executable", "", "Executables (*.exe)")
        if path:
            self.reader_input.setText(path)

    def save_settings(self):
        import config
        
        APP_SETTINGS["cv_key"]      = self.cv_input.text().strip()
        APP_SETTINGS["gemini_key"]  = self.gem_input.text().strip()
        APP_SETTINGS["reader_path"] = self.reader_input.text().strip()
        APP_SETTINGS["chat_voice"]  = self.voice_combo.currentText()
        APP_SETTINGS["chat_speed"]  = self.speed_slider.value()
        
        config.COMIC_VINE_KEY = APP_SETTINGS["cv_key"]
        config.GEMINI_KEY = APP_SETTINGS["gemini_key"]
        
        with open("settings.json", "w") as f:
            json.dump(APP_SETTINGS, f)
            
        QMessageBox.information(self, "Saved", "Settings saved successfully!\n(API key changes take effect on next restart or new search).")


# ==============================================================================
# SILENT WEB PAGE
# ==============================================================================
class SilentWebPage(QWebEnginePage):
    # This overrides the default behavior and tells PyQt to completely
    # ignore all JavaScript console messages from the website!
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        pass



# ==============================================================================
# BATCH AUTO REVIEW DIALOG
# ==============================================================================
class BatchAutoReviewDialog(QDialog):
    """Post-run review: files already written. Fix bad matches by re-searching and overwriting."""

    def __init__(self, matches, parent=None):
        super().__init__(parent)
        self.matches    = matches
        self.index      = 0
        self.img_thread = None
        self.search_thread = None
        self.issue_thread = None
        self._pending_result = None
        self._load_id = 0  # Increment on each load to ignore stale async callbacks

        self.setWindowTitle("🏷️ Review Auto-Tagged Results")
        self.setMinimumSize(1000, 660)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog   { background-color: #1e1f29; color: #f8f8f2; }
            QLabel    { color: #f8f8f2; }
            QLineEdit { background-color: #21222c; border: 1px solid #44475a;
                        padding: 5px; color: #f8f8f2; border-radius: 4px; }
            QListWidget { background-color: #21222c; border: 1px solid #44475a;
                          color: #f8f8f2; font-size: 13px; }
            QListWidget::item:selected { background-color: #6272a4; }
            QPushButton { border-radius: 4px; padding: 8px 16px; font-weight: bold; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        self.counter_lbl = QLabel()
        self.counter_lbl.setStyleSheet("color: #8be9fd; font-size: 13px;")
        top_row.addWidget(self.counter_lbl)
        top_row.addStretch()
        note = QLabel("✅ All files already written — Re-search + Overwrite to fix bad matches")
        note.setStyleSheet("color: #6272a4; font-size: 11px;")
        top_row.addWidget(note)
        root.addLayout(top_row)

        body = QHBoxLayout()
        body.setSpacing(16)

        left = QVBoxLayout()
        QLabel_local = QLabel("Your File")
        QLabel_local.setStyleSheet("color: #6272a4; font-size: 11px; font-weight: bold;")
        left.addWidget(QLabel_local)
        self.local_cover = QLabel()
        self.local_cover.setFixedSize(220, 330)
        self.local_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.local_cover.setStyleSheet("background:#21222c; border:1px solid #44475a; border-radius:4px;")
        left.addWidget(self.local_cover)
        self.local_name = QLabel()
        self.local_name.setWordWrap(True)
        self.local_name.setMaximumWidth(220)
        self.local_name.setStyleSheet("color:#f8f8f2; font-size:11px;")
        left.addWidget(self.local_name)
        left.addStretch()
        body.addLayout(left)

        centre = QVBoxLayout()
        centre.setSpacing(6)

        self.status_badge = QLabel("✅ Written")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setStyleSheet(
            "background:#253320; color:#50fa7b; border-radius:4px; padding:6px 12px; font-size:13px;")
        centre.addWidget(self.status_badge)

        self.match_info = QLabel()
        self.match_info.setWordWrap(True)
        self.match_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.match_info.setStyleSheet("color:#50fa7b; font-size:13px; font-weight:bold;")
        centre.addWidget(self.match_info)

        self.search_box = QWidget()
        sb = QVBoxLayout(self.search_box)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(4)
        sr = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Comic Vine…")
        self.search_input.returnPressed.connect(self._do_search)
        self.search_go_btn = QPushButton("Search")
        self.search_go_btn.setStyleSheet("background:#44475a; color:#f8f8f2; padding:6px 10px;")
        self.search_go_btn.clicked.connect(self._do_search)
        sr.addWidget(self.search_input)
        sr.addWidget(self.search_go_btn)
        sb.addLayout(sr)
        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(180)
        self.results_list.itemClicked.connect(self._on_result_selected)
        sb.addWidget(self.results_list)
        self.overwrite_btn = QPushButton("✏️ Overwrite File with Selected")
        self.overwrite_btn.setStyleSheet("background:#ff79c6; color:#282a36; font-size:13px;")
        self.overwrite_btn.setEnabled(False)
        self.overwrite_btn.clicked.connect(self._overwrite)
        sb.addWidget(self.overwrite_btn)
        self.search_box.hide()
        centre.addWidget(self.search_box)
        centre.addStretch()
        body.addLayout(centre, stretch=1)

        right = QVBoxLayout()
        QLabel_cv = QLabel("Comic Vine Match")
        QLabel_cv.setStyleSheet("color: #6272a4; font-size: 11px; font-weight: bold;")
        right.addWidget(QLabel_cv)
        self.cv_cover = QLabel()
        self.cv_cover.setFixedSize(220, 330)
        self.cv_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cv_cover.setStyleSheet("background:#21222c; border:1px solid #44475a; border-radius:4px;")
        right.addWidget(self.cv_cover)
        self.cv_name = QLabel()
        self.cv_name.setWordWrap(True)
        self.cv_name.setMaximumWidth(220)
        self.cv_name.setStyleSheet("color:#f8f8f2; font-size:11px;")
        right.addWidget(self.cv_name)
        right.addStretch()
        body.addLayout(right)

        root.addLayout(body, stretch=1)

        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.back_btn = QPushButton("◀ Back")
        self.back_btn.setStyleSheet("background:#44475a; color:#f8f8f2;")
        self.back_btn.clicked.connect(self._go_back)
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setStyleSheet("background:#44475a; color:#f8f8f2;")
        self.next_btn.clicked.connect(self._go_next)
        self.research_btn = QPushButton("🔍 Re-search")
        self.research_btn.setStyleSheet("background:#bd93f9; color:#282a36;")
        self.research_btn.clicked.connect(self._toggle_search)
        done_btn = QPushButton("✅ Done")
        done_btn.setStyleSheet("background:#50fa7b; color:#282a36; font-size:14px; padding:10px 20px;")
        done_btn.clicked.connect(self.accept)
        nav.addWidget(self.back_btn)
        nav.addWidget(self.next_btn)
        nav.addStretch()
        nav.addWidget(self.research_btn)
        nav.addStretch()
        nav.addWidget(done_btn)
        root.addLayout(nav)

        self._load_match()

    def _stop_img_thread(self):
        if self.img_thread and self.img_thread.isRunning():
            self.img_thread.quit()
            self.img_thread.wait(3000)

    def _stop_issue_thread(self):
        if self.issue_thread and self.issue_thread.isRunning():
            self.issue_thread.quit()
            self.issue_thread.wait(3000)

    def _stop_search_thread(self):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.quit()
            self.search_thread.wait(3000)

    def closeEvent(self, event):
        self._stop_img_thread()
        self._stop_issue_thread()
        self._stop_search_thread()
        super().closeEvent(event)

    def _current(self):
        return self.matches[self.index]

    def _load_match(self):
        m = self._current()
        total = len(self.matches)
        self.counter_lbl.setText(f"Match {self.index + 1} of {total}")
        self.back_btn.setEnabled(self.index > 0)
        self.next_btn.setEnabled(self.index < total - 1)

        if m.get('overwritten'):
            self.status_badge.setText("✏️ Overwritten")
            self.status_badge.setStyleSheet(
                "background:#1a2a3a; color:#8be9fd; border-radius:4px; padding:6px 12px; font-size:13px;")
        else:
            self.status_badge.setText("✅ Written")
            self.status_badge.setStyleSheet(
                "background:#253320; color:#50fa7b; border-radius:4px; padding:6px 12px; font-size:13px;")

        idata = m.get('issue_data') or {}
        vol_name = (idata.get('volume') or {}).get('name', '')
        num  = idata.get('issue_number', '')
        name = idata.get('name', '')
        date = idata.get('cover_date', '')
        info_parts = []
        if vol_name: info_parts.append(f"{vol_name} #{num}" if num else vol_name)
        if name:     info_parts.append(name)
        if date:     info_parts.append(f"📅 {date}")
        info_text = "\n".join(info_parts)
        self.match_info.setText(info_text)
        self.cv_name.setText(info_text)

        self.local_name.setText(m['filename'])
        self.local_cover.setText("No cover")
        if m.get('local_bytes'):
            pix = QPixmap()
            if pix.loadFromData(m['local_bytes']):
                self.local_cover.setPixmap(
                    pix.scaled(220, 330, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation))

        self.cv_cover.setText("Loading…")
        if m.get('cv_bytes'):
            pix = QPixmap()
            if pix.loadFromData(m['cv_bytes']):
                self.cv_cover.setPixmap(
                    pix.scaled(220, 330, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation))
        else:
            url = m.get('cv_cover_url', '')
            if not url:
                try:
                    img = (m.get('issue_data') or {}).get('image') or {}
                    url = img.get('medium_url') or img.get('small_url') or ''
                except Exception:
                    pass
            if url:
                self._stop_img_thread()
                self.img_thread = ImageDownloadThread(url)
                idx = self.index
                def _got(data, i=idx, match=m):
                    if self.index != i: return
                    match['cv_bytes'] = data
                    pix = QPixmap()
                    if pix.loadFromData(data):
                        self.cv_cover.setPixmap(
                            pix.scaled(220, 330, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation))
                self.img_thread.image_ready.connect(_got)
                self.img_thread.start()
            else:
                self.cv_cover.setText("No cover")

        self.search_box.hide()
        self.research_btn.setText("🔍 Re-search")
        self.results_list.clear()
        self.overwrite_btn.setEnabled(False)
        self._pending_result = None

    def _go_back(self):
        if self.index > 0:
            self.index -= 1
            self._load_match()

    def _go_next(self):
        if self.index < len(self.matches) - 1:
            self.index += 1
            self._load_match()

    def _toggle_search(self):
        if self.search_box.isVisible():
            self.search_box.hide()
            self.research_btn.setText("🔍 Re-search")
        else:
            self.search_box.show()
            m = self._current()
            base = os.path.splitext(m['filename'])[0]
            # Use the same parser the batch tagger uses so the query is clean
            parsed = parse_comic_filename_full(base)
            series = parsed.get('series', '')
            issue  = parsed.get('issue', '')
            year   = parsed.get('year', '')
            if issue:
                query = f"{series} {issue} {year}".strip()
            elif parsed.get('subtitle'):
                query = f"{series} {parsed['subtitle']} {year}".strip()
            else:
                query = f"{series} {year}".strip()
            self.search_input.setText(query)
            self.results_list.clear()
            self.overwrite_btn.setEnabled(False)
            self._pending_result = None
            self.research_btn.setText("✖ Close Search")
            # Auto-trigger the search immediately
            self._do_search()

    def _do_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self.results_list.clear()
        self.results_list.addItem("🔍 Searching Comic Vine…")
        self.overwrite_btn.setEnabled(False)
        self._pending_result = None
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.quit()
            self.search_thread.wait(1000)
        self.search_thread = ComicVineIssueSearchThread(query)
        self.search_thread.results_ready.connect(self._on_search_results)
        self.search_thread.start()

    def _on_search_results(self, results):
        self.results_list.clear()
        if not results:
            self.results_list.addItem("❌ No issues found.")
            return
        for r in results:
            vol = r.get("volume") or {}
            vol_name = vol.get("name", "Unknown")
            num = r.get("issue_number", "?")
            date = r.get("cover_date", "")[:10] if r.get("cover_date") else ""
            label = f"{vol_name} #{num}" + (f"  •  {date}" if date else "")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.results_list.addItem(item)

    def _on_result_selected(self, item):
        if not item:
            return
        issue_data = item.data(Qt.ItemDataRole.UserRole)
        if not issue_data:
            return
        api_url = issue_data.get("api_detail_url")
        if api_url:
            self.cv_cover.setText("Loading…")
            self.overwrite_btn.setEnabled(False)
            self._pending_result = None
            if self.issue_thread and self.issue_thread.isRunning():
                self.issue_thread.quit()
                self.issue_thread.wait(1000)
            self.issue_thread = ComicVineIssueThread(direct_api_url=api_url)
            self.issue_thread.issue_ready.connect(self._on_full_issue_loaded)
            self.issue_thread.start()
        else:
            self._pending_result = issue_data
            self.overwrite_btn.setEnabled(True)
            self._show_result_cover(issue_data)

    def _on_full_issue_loaded(self, full_data):
        if not full_data:
            self.cv_cover.setText("Load failed")
            return
        self._pending_result = full_data
        self.overwrite_btn.setEnabled(True)
        self._show_result_cover(full_data)

    def _show_result_cover(self, issue_data):
        url = (issue_data.get("image") or {}).get("medium_url") or (issue_data.get("image") or {}).get("small_url") or ""
        vol = issue_data.get("volume") or {}
        self.cv_name.setText(f"{vol.get('name', '')} #{issue_data.get('issue_number', '')}")
        if url:
            if self.img_thread and self.img_thread.isRunning():
                self.img_thread.quit()
                self.img_thread.wait(1000)
            self.img_thread = ImageDownloadThread(url)
            self.img_thread.image_ready.connect(self._on_cover_loaded)
            self.img_thread.start()
        else:
            self.cv_cover.setText("No cover")

    def _on_cover_loaded(self, data):
        if not data:
            self.cv_cover.setText("Load failed")
            return
        pix = QPixmap()
        if pix.loadFromData(data):
            self.cv_cover.setPixmap(
                pix.scaled(220, 330, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation))
        else:
            self.cv_cover.setText("No cover")

    def _overwrite(self):
        if not self._pending_result:
            return
        m = self._current()
        path = m.get("path") or m.get("file_path")
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "Overwrite Failed", "File not found.")
            return
        try:
            xml_str = generate_comicinfo_xml(self._pending_result, path)
            inject_metadata_into_cbz(path, xml_str)
            m["issue_data"] = self._pending_result
            m["overwritten"] = True
            self._pending_result = None
            self.overwrite_btn.setEnabled(False)
            self._load_match()
        except Exception as e:
            QMessageBox.critical(self, "Overwrite Failed", str(e))


# ==============================================================================
# BATCH TAGGER TAB
# ==============================================================================
class BatchTaggerTab(QWidget):
    def __init__(self):
        super().__init__()
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        
        self.header = QLabel("🏷️ Batch Comic Tagger & CBR Converter")
        self.header.setStyleSheet("color: #ffb86c; font-weight: bold; font-size: 16px;")
        self.layout.addWidget(self.header)
        
        controls_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Add one or more folders full of comics...")
        self.folder_input.setReadOnly(True)
        
        self.browse_btn = QPushButton("➕ Add Folder")
        self.browse_btn.clicked.connect(self.browse_folder)
        
        self.clear_btn = QPushButton("🗑️ Clear Selection")
        self.clear_btn.clicked.connect(self.clear_folders)
        
        self.start_btn = QPushButton("Start Tagging")
        self.start_btn.setStyleSheet("background-color: #ff79c6; color: #282a36; font-weight: bold;")
        self.start_btn.clicked.connect(self.start_tagging)
        self.start_btn.setEnabled(False)

        # --- NEW: The Stop Button ---
        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.setStyleSheet("background-color: #ff5555; color: white; font-weight: bold;")
        self.stop_btn.clicked.connect(self.stop_tagging)
        self.stop_btn.setEnabled(False)

        controls_layout.addWidget(self.folder_input)
        controls_layout.addWidget(self.browse_btn)
        controls_layout.addWidget(self.clear_btn)
        controls_layout.addWidget(self.start_btn)
        controls_layout.addWidget(self.stop_btn)
        self.layout.addLayout(controls_layout)
        
        # --- THE NEW OPTIONS ROW ---
        options_layout = QHBoxLayout()
        self.interactive_cb = QCheckBox("Interactive Mode (Confirm Matches)")
        self.interactive_cb.setChecked(True)
        
        self.overwrite_cb = QCheckBox("Overwrite Existing Metadata")
        self.overwrite_cb.setChecked(False)
        self.overwrite_cb.setStyleSheet("color: #ff5555; font-weight: bold;")

        self.ai_summary_cb = QCheckBox("AI Summaries (auto-fill missing summaries via Gemini)")
        self.ai_summary_cb.setChecked(False)
        self.ai_summary_cb.setStyleSheet("color: #bd93f9; font-weight: bold;")
        
        options_layout.addWidget(self.interactive_cb)
        options_layout.addWidget(self.overwrite_cb)
        options_layout.addWidget(self.ai_summary_cb)
        options_layout.addStretch()
        self.layout.addLayout(options_layout)
        
        # --- THE NEW URL FORCE BOX ---
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Optional: Force Comic Vine Volume URLs (comma separated)... e.g. https://comicvine.gamespot.com/action-comics/4050-42563/")
        self.layout.addWidget(self.url_input)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)
        
        self.log_display = QTextBrowser()
        self.log_display.setStyleSheet("background-color: #282a36; color: #f8f8f2; font-family: Consolas;")
        self.layout.addWidget(self.log_display)
        
        self.selected_folders = [] 
        self.cbz_files = []        
        self.tagger_thread = None

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Add Comic Folder")
        
        if folder:
            if folder not in self.selected_folders:
                self.selected_folders.append(folder)
                
            self.folder_input.setText("; ".join(self.selected_folders))
            
            new_files = [os.path.join(folder, f) for f in os.listdir(folder) 
                         if f.lower().endswith('.cbz') or f.lower().endswith('.cbr')]
            
            for nf in new_files:
                if nf not in self.cbz_files:
                    self.cbz_files.append(nf)
            
            self.log_display.append(f"📁 Added Folder: {folder}")
            self.log_display.append(f"📊 Total files ready for processing: {len(self.cbz_files)}\n")
            
            if self.cbz_files:
                self.start_btn.setEnabled(True)
                self.progress_bar.setMaximum(len(self.cbz_files))

    def receive_folder(self, folder: str):
        """Called externally (e.g. right-click menu) to add a folder to the tagger."""
        folder = os.path.normpath(folder)
        if not os.path.isdir(folder):
            folder = os.path.dirname(folder)

        if folder not in self.selected_folders:
            self.selected_folders.append(folder)

        self.folder_input.setText("; ".join(self.selected_folders))

        new_files = [
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith(('.cbz', '.cbr'))
        ]
        added = 0
        for nf in new_files:
            if nf not in self.cbz_files:
                self.cbz_files.append(nf)
                added += 1

        self.log_display.append(f"📤 Received from browser: {folder}")
        self.log_display.append(f"📊 Added {added} file(s) — Total: {len(self.cbz_files)}\n")

        if self.cbz_files:
            self.start_btn.setEnabled(True)
            self.progress_bar.setMaximum(len(self.cbz_files))

    def clear_folders(self):
        self.selected_folders.clear()
        self.cbz_files.clear()
        self.folder_input.clear()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_display.clear()
        self.log_display.append("🗑️ Selection cleared. Add a folder to begin.\n")

    def start_tagging(self):
        if not COMIC_VINE_KEY:
            QMessageBox.warning(self, "Missing API Key", "Please add your Comic Vine API Key in the Settings tab first!")
            return
            
        self.start_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.interactive_cb.setEnabled(False) 
        self.overwrite_cb.setEnabled(False)
        self.ai_summary_cb.setEnabled(False)
        self.url_input.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        self.progress_bar.setValue(0)
        self.log_display.append("🚀 Starting Batch Tagger...\n")
        
        self.tagger_thread = BatchTaggerThread(
            self.cbz_files, 
            self.interactive_cb.isChecked(),
            self.overwrite_cb.isChecked(),
            self.url_input.text().strip(),
            self.ai_summary_cb.isChecked()
        )
        self.tagger_thread.progress_update.connect(self.update_log)
        self.tagger_thread.finished.connect(self.tagging_finished)
        self.tagger_thread.needs_confirmation.connect(self.handle_confirmation, Qt.ConnectionType.QueuedConnection)
        self.tagger_thread.matches_collected.connect(self.show_auto_review, Qt.ConnectionType.QueuedConnection)
        
        self.tagger_thread.start()

    # --- NEW: The Stop Function ---
    def stop_tagging(self):
        if self.tagger_thread and self.tagger_thread.isRunning():
            self.stop_btn.setEnabled(False)
            self.log_display.append("\n⏳ Stopping... (Waiting for current file to safely finish writing)")
            self.tagger_thread.stop()
            
    def update_log(self, current_index, message):
        self.progress_bar.setValue(current_index)
        self.progress_bar.setFormat("%v of %m comics")
        self.log_display.append(message)

    def tagging_finished(self):
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.interactive_cb.setEnabled(True)
        self.overwrite_cb.setEnabled(True)
        self.ai_summary_cb.setEnabled(True)
        self.url_input.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(self.progress_bar.maximum())

    def show_auto_review(self, matches):
        if not matches:
            return
        dlg = BatchAutoReviewDialog(matches, self)
        dlg.exec()

    def handle_confirmation(self, filename, results, local_cover_bytes):
        try:
            dialog = BatchCoverMatchDialog(filename, results, local_cover_bytes, self)
            if dialog.exec() == 1: 
                self.tagger_thread.user_choice = dialog.selected_data
            else:
                self.tagger_thread.user_choice = None 
        except Exception as e:
            self.log_display.append(f"❌ Dialog Error on {filename}: {str(e)}")
            self.tagger_thread.user_choice = None 
        finally:
            self.tagger_thread.wait_event.set()


# ==============================================================================
# GET COMICS TAB
# ==============================================================================
class GetComicsTab(QWidget):
    download_completed = pyqtSignal(str, bool)   # emits (article URL, via_hoster)
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Top Navigation Bar ---
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(10, 10, 10, 5)
        
        self.back_btn = QPushButton("◄ Back")
        self.back_btn.clicked.connect(self.go_back)
        
        self.forward_btn = QPushButton("Forward ►")
        self.forward_btn.clicked.connect(self.go_forward)
        
        self.reload_btn = QPushButton("🔄 Reload")
        self.reload_btn.clicked.connect(self.reload_page)
        
        self.url_bar = QLineEdit()
        self.url_bar.setText("https://getcomics.org/") 
        self.url_bar.returnPressed.connect(self.load_url)
        
        self.go_btn = QPushButton("Go")
        self.go_btn.clicked.connect(self.load_url)

        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.forward_btn)
        nav_layout.addWidget(self.reload_btn)
        nav_layout.addWidget(self.url_bar)
        nav_layout.addWidget(self.go_btn)
        self.layout.addLayout(nav_layout)
        
       # --- The Web Browser ---
        self.browser = QWebEngineView()
        
        # Apply our custom ad-muting page!
        self.silent_page = SilentWebPage(self.browser)
        self.browser.setPage(self.silent_page)
        
        self.browser.setUrl(QUrl("https://getcomics.info/"))
        self.browser.urlChanged.connect(self.update_url_bar)
        self.layout.addWidget(self.browser, 1)

        # --- Bottom Status Bar (Zoom & Download) ---
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 5, 10, 10)
        
        # Zoom Controls
        self.zoom_label = QLabel("Zoom: 100%")
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(5, 30) 
        self.zoom_slider.setValue(10) 
        self.zoom_slider.setFixedWidth(150)
        self.zoom_slider.valueChanged.connect(self.change_zoom)
        
        bottom_layout.addWidget(QLabel("🔍"))
        bottom_layout.addWidget(self.zoom_slider)
        bottom_layout.addWidget(self.zoom_label)
        
        bottom_layout.addStretch() 
        
        # Download Progress
        self.dl_status_label = QLabel("")
        self.dl_status_label.setStyleSheet("color: #f1fa8c;")
        self.dl_progress = QProgressBar()
        self.dl_progress.setFixedWidth(250)
        self.dl_progress.setVisible(False) 
        
        bottom_layout.addWidget(self.dl_status_label)
        bottom_layout.addWidget(self.dl_progress)
        self.layout.addLayout(bottom_layout)
        
        # --- The Download Catcher ---
        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(self.handle_download)
        self.current_download   = None
        self._current_dl_url    = ""
        self._origin_article_url = ""
        self._last_getcomics_article_url = ""
        self._current_dl_via_hoster = False

    def go_back(self): self.browser.back()
    def go_forward(self): self.browser.forward()
    def reload_page(self): self.browser.reload()

    def load_url(self):
        url_text = self.url_bar.text().strip()
        if not url_text.startswith("http"):
            url_text = "https://" + url_text
        self.browser.setUrl(QUrl(url_text))

    def update_url_bar(self, qurl):
        url = qurl.toString()
        self.url_bar.setText(url)
        # Keep the last GetComics article URL so host redirects (VikingFile/PixelDrain)
        # can still map completion back to the original article.
        low = url.lower()
        if ("getcomics." in low or "getcomics.org" in low) and "/sitemap" not in low:
            self._last_getcomics_article_url = url

    def set_origin_article_url(self, url: str):
        """Track the originating GetComics article URL across redirects (e.g., VikingFile)."""
        self._origin_article_url = (url or "").strip()

    def change_zoom(self, value):
        factor = value / 10.0
        self.zoom_label.setText(f"Zoom: {int(factor * 100)}%")
        self.browser.setZoomFactor(factor)

    def handle_download(self, download):
        default_name = download.downloadFileName()
        # Remember last download directory across sessions
        last_dir = APP_SETTINGS.get("last_dl_dir", "")
        suggested = os.path.join(last_dir, default_name) if last_dir else default_name
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Comic", suggested)

        if save_path:
            save_dir = os.path.dirname(save_path)
            APP_SETTINGS["last_dl_dir"] = save_dir
            try:
                with open("settings.json", "w") as f:
                    json.dump(APP_SETTINGS, f)
            except Exception:
                pass

            download.setDownloadDirectory(save_dir)
            download.setDownloadFileName(os.path.basename(save_path))

            self.current_download   = download
            # Use the best article URL source when downloads are triggered on redirect hosts
            # like VikingFile/PixelDrain.
            self._current_dl_url = (
                self._origin_article_url
                or self._last_getcomics_article_url
                or self.url_bar.text()
            )

            # Detect whether the download came from a hoster we care about.
            dl_url = ""
            try:
                dl_url = download.url().toString()
            except Exception:
                dl_url = ""
            if not dl_url:
                try:
                    dl_url = download.downloadUrl().toString()
                except Exception:
                    dl_url = ""

            low_dl = (dl_url or "").lower()
            low_bar = (self.url_bar.text() or "").lower()
            self._current_dl_via_hoster = any(x in low_dl for x in ("mega.nz", "rootz", "terabox")) or \
                                            any(x in low_bar for x in ("mega.nz", "rootz", "terabox"))

            download.receivedBytesChanged.connect(self.update_dl_progress)
            download.stateChanged.connect(self.dl_state_changed)

            self.dl_progress.setValue(0)
            self.dl_progress.setVisible(True)

            display_name = default_name if len(default_name) < 40 else default_name[:37] + "..."
            self.dl_status_label.setText(f"Downloading: {display_name}")

            download.accept()
            
    def update_dl_progress(self):
        if self.current_download:
            bytes_received = self.current_download.receivedBytes()
            bytes_total = self.current_download.totalBytes()
            
            if bytes_total > 0:
                percentage = int((bytes_received / bytes_total) * 100)
                self.dl_progress.setValue(percentage)
            
    def dl_state_changed(self, state):
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.dl_status_label.setText("✅ Download Complete!")
            self.dl_progress.setVisible(False)
            if self._current_dl_url:
                self.download_completed.emit(self._current_dl_url, self._current_dl_via_hoster)
                self._current_dl_url = ""
                self._current_dl_via_hoster = False
        elif state in (QWebEngineDownloadRequest.DownloadState.DownloadCancelled,
                       QWebEngineDownloadRequest.DownloadState.DownloadInterrupted):
            self.dl_status_label.setText("❌ Download Failed/Cancelled.")
            self.dl_progress.setVisible(False)
            self._current_dl_via_hoster = False


# ==============================================================================
# COVER SELECTION DIALOG
# ==============================================================================
class CoverSelectionDialog(QDialog):
    def __init__(self, images_bytes, parent=None):
        
        super().__init__(parent)
        self.setWindowTitle("Select a Cover")
        self.resize(800, 450)
        self.setStyleSheet("QDialog { background-color: #282a36; color: white; }")
        self.layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(180, 270))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setSpacing(10)
        self.list_widget.setStyleSheet("background-color: #21222c; border: 1px solid #44475a; color: white;")

        self.images_bytes = images_bytes
        self.selected_bytes = None

        for i, img_bytes in enumerate(images_bytes):
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes)
            icon = QIcon(pixmap.scaled(180, 270, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            item = QListWidgetItem(f"Option {i+1}")
            item.setIcon(icon)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list_widget.addItem(item)

        self.layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("✅ Set as Cover")
        self.ok_btn.setStyleSheet("background-color: #50fa7b; color: #282a36; font-weight: bold; padding: 10px;")
        self.ok_btn.clicked.connect(self.accept_selection)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.setStyleSheet("background-color: #ff5555; color: white; font-weight: bold; padding: 10px;")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        self.layout.addLayout(btn_layout)

    def accept_selection(self):
        curr = self.list_widget.currentItem()
        if curr:
            idx = curr.data(Qt.ItemDataRole.UserRole)
            self.selected_bytes = self.images_bytes[idx]
            self.accept()
        else:
            QMessageBox.warning(self, "Select", "Please select an image first.")
            


# ==============================================================================
# COMIC METADATA DIALOG
# ==============================================================================
class ComicMetadataDialog(QDialog):
    """Shows all ComicInfo.xml fields and lets the user edit any of them."""

    # Every standard ComicInfo field we support, as (xml_tag, display_label) pairs.
    FIELDS = [
        ("Series",          "Series"),
        ("Number",          "Issue #"),
        ("Volume",          "Volume"),
        ("Title",           "Title"),
        ("AlternateSeries", "Alternate Series"),
        ("AlternateNumber", "Alt. Number"),
        ("AlternateCount",  "Alt. Count"),
        ("StoryArc",        "Story Arc"),
        ("Summary",         "Summary"),
        ("Notes",           "Notes"),
        ("Year",            "Year"),
        ("Month",           "Month"),
        ("Day",             "Day"),
        ("Writer",          "Writer"),
        ("Penciller",       "Penciller"),
        ("Inker",           "Inker"),
        ("Colorist",        "Colorist"),
        ("Letterer",        "Letterer"),
        ("CoverArtist",     "Cover Artist"),
        ("Editor",          "Editor"),
        ("Publisher",       "Publisher"),
        ("Imprint",         "Imprint"),
        ("Genre",           "Genre"),
        ("Web",             "Web URL"),
        ("PageCount",       "Page Count"),
        ("LanguageISO",     "Language"),
        ("Format",          "Format"),
        ("AgeRating",       "Age Rating"),
        ("Characters",      "Characters"),
        ("Teams",           "Teams"),
        ("Locations",       "Locations"),
        ("ScanInformation", "Scan Info"),
        ("SeriesGroup",     "Series Group"),
        ("PlayCount",       "Play Count"),
    ]

    # Fields that get a tall QTextEdit instead of a single-line QLineEdit
    MULTILINE = {"Summary", "Notes", "Characters", "Teams", "Locations", "ScanInformation"}

    def __init__(self, xml_str: str, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.xml_str   = xml_str
        self._editing  = False

        self.setWindowTitle(f"Metadata — {os.path.basename(file_path)}")
        self.resize(640, 720)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog          { background-color: #282a36; color: #f8f8f2; }
            QLabel           { color: #f8f8f2; }
            QLineEdit, QTextEdit {
                background-color: #21222c;
                border: 1px solid #44475a;
                color: #f8f8f2;
                padding: 4px;
                border-radius: 3px;
            }
            QLineEdit:read-only, QTextEdit:read-only {
                background-color: #1e1f29;
                border: 1px solid #383a4a;
                color: #a0a0b0;
            }
            QPushButton {
                background-color: #44475a;
                color: #f8f8f2;
                padding: 6px 14px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #6272a4; }
            QPushButton#edit_btn  { background-color: #ffb86c; color: #282a36; }
            QPushButton#save_btn  { background-color: #50fa7b; color: #282a36; }
            QScrollArea { border: none; }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 10)
        root_layout.setSpacing(8)

        # ── Header ──
        hdr = QLabel(f"<b style='color:#8be9fd; font-size:14px;'>{os.path.basename(file_path)}</b>")
        root_layout.addWidget(hdr)

        # ── Scroll area for all fields ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background-color: #282a36; border: none; }")
        inner = QWidget()
        inner.setStyleSheet("background-color: #282a36;")
        self.form = QFormLayout(inner)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.form.setSpacing(6)
        scroll.setWidget(inner)
        root_layout.addWidget(scroll, 1)

        # ── Parse XML and populate fields ──
        try:
            clean = re.sub(r'\sxmlns="[^"]+"', '', xml_str, count=1)
            root_el = ET.fromstring(clean)
        except Exception:
            root_el = None

        self._widgets = {}   # tag -> widget
        for tag, label in self.FIELDS:
            value = root_el.findtext(tag, "") if root_el is not None else ""
            if tag in self.MULTILINE:
                w = QTextEdit()
                w.setPlainText(value)
                w.setFixedHeight(72)
                w.setReadOnly(True)
            else:
                w = QLineEdit(value)
                w.setReadOnly(True)
            self._widgets[tag] = w
            lbl = QLabel(label + ":")
            lbl.setStyleSheet("color: #bd93f9;" if value.strip() else "color: #555577;")
            self.form.addRow(lbl, w)

        # ── Button row ──
        btn_row = QHBoxLayout()

        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.setObjectName("edit_btn")
        self.edit_btn.clicked.connect(self._toggle_edit)

        self.save_btn = QPushButton("💾 Save Changes")
        self.save_btn.setObjectName("save_btn")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_changes)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        root_layout.addLayout(btn_row)

    # ── Edit toggle ──
    def _toggle_edit(self):
        self._editing = not self._editing
        for w in self._widgets.values():
            if isinstance(w, QTextEdit):
                w.setReadOnly(not self._editing)
            else:
                w.setReadOnly(not self._editing)
        self.edit_btn.setText("🔒 Lock" if self._editing else "✏️ Edit")
        self.save_btn.setEnabled(self._editing)

    # ── Build updated XML from current widget values ──
    def _build_xml(self) -> str:
        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" ',
            '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
        ]
        for tag, _ in self.FIELDS:
            w = self._widgets[tag]
            value = w.toPlainText().strip() if isinstance(w, QTextEdit) else w.text().strip()
            if value:
                lines.append(f'  <{tag}>{html.escape(value)}</{tag}>')
        lines.append("</ComicInfo>")
        return "\n".join(lines)

    # ── Write back to the CBZ ──
    def _save_changes(self):
        new_xml = self._build_xml()
        try:
            inject_metadata_into_cbz(self.file_path, new_xml)
            QMessageBox.information(self, "Saved", "Metadata updated successfully!")
            self.xml_str = new_xml   # keep in sync
            self._toggle_edit()      # back to read-only
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save metadata:\n{e}")


# ==============================================================================
# COMIC BROWSER
# ==============================================================================
class ComicBrowser(QMainWindow):
    def on_tree_right_click(self, position):
        
        index = self.tree.indexAt(position)
        if not index.isValid():
            return
            
        source_index = self.proxy_model.mapToSource(index)
        path = self.model.filePath(source_index)
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #282a36; color: #f8f8f2; border: 1px solid #44475a; } 
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #44475a; }
        """)
        
        open_action = menu.addAction("📂 Open in File Explorer")
        tagger_action = menu.addAction("🏷️ Send to Tagger")

        action = menu.exec(self.tree.viewport().mapToGlobal(position))

        if action == open_action:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            try:
                os.startfile(folder)
            except Exception as e:
                print(f"Could not open folder: {e}")
        elif action == tagger_action:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            self._ensure_tab_built(self._TAB_TAGGER)
            self.tagger_tab.receive_folder(folder)
            self.tabs.setCurrentIndex(self._TAB_TAGGER)
    def grid_go_up(self):
        if not getattr(self, 'current_grid_folder', None): return
        parent_dir = os.path.dirname(self.current_grid_folder)
        # Prevent crashing if we hit the root drive (e.g. C:\)
        if parent_dir != self.current_grid_folder and os.path.exists(parent_dir):
            self.forward_grid_folder = self.current_grid_folder # Save child folder to jump back down
            self._is_navigating_up = True
            self.load_folder_grid(parent_dir)

    def grid_go_forward(self):
        target = getattr(self, 'forward_grid_folder', None)
        if target and os.path.exists(target):
            self.forward_grid_folder = None # Clear it once used
            self.load_folder_grid(target)

    def load_folder_grid(self, folder_path):
        
        # --- NEW HISTORY TRACKING ---
        norm_path = os.path.normpath(folder_path)
        # If we clicked a completely new folder, wipe the forward history so we don't jump somewhere weird!
        if not getattr(self, '_is_navigating_up', False) and norm_path != getattr(self, 'forward_grid_folder', None):
            self.forward_grid_folder = None
            
        self.current_grid_folder = norm_path
        self._is_navigating_up = False
        # ----------------------------
        
        self.grid_list.clear()
        self.grid_items_map.clear()
        self.grid_folder_map = getattr(self, 'grid_folder_map', {})
        self.grid_folder_map.clear()
        
        if hasattr(self, 'refresh_cbl_btn'): self.refresh_cbl_btn.hide()
        if hasattr(self, 'cbl_stats_label'): self.cbl_stats_label.hide()

        if getattr(self, 'cover_thread', None) and self.cover_thread.isRunning():
            self.cover_thread.stop()
            self.cover_thread.wait()
            
        if getattr(self, 'folder_cover_thread', None) and self.folder_cover_thread.isRunning():
            self.folder_cover_thread.stop()
            self.folder_cover_thread.wait()

        comic_files = []
        directory_items = [] 
        self.grid_list.setUpdatesEnabled(False)
        
        try:
            files = os.listdir(folder_path)
            
            def natural_sort_key(s):
                return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
            files.sort(key=natural_sort_key)
            
            cbl_files = []
            for file in files:
                full_path = os.path.normpath(os.path.join(folder_path, file))
                if full_path in getattr(self, 'hidden_paths', set()): 
                    continue
                if os.path.isdir(full_path): directory_items.append((file, full_path))
                elif file.lower().endswith(('.cbz', '.cbr')): comic_files.append(full_path)
                elif file.lower().endswith('.cbl'): cbl_files.append(full_path)

            # --- 1. DRAW FOLDERS (Placeholder Stacks) ---
            folders_to_load = []
            for dir_name, dir_path in directory_items:
                item = QListWidgetItem(dir_name)
                item.setData(Qt.ItemDataRole.UserRole, f"FOLDER:{dir_path}")
                
                pixmap = QPixmap(180, 270)
                pixmap.fill(Qt.GlobalColor.transparent) 
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                colors = ["#21222c", "#282a36", "#44475a", "#6272a4", "#8be9fd"]
                w, h = 140, 210 
                
                for i in range(5):
                    painter.setBrush(QColor(colors[i]))
                    painter.setPen(QColor("#f8f8f2") if i == 4 else QColor("#1e1f29"))
                    painter.drawRect(i * 8, i * 12, w, h)
                    if i == 4:
                        painter.setPen(QColor("#282a36"))
                        font = painter.font(); font.setBold(True); font.setPointSize(10)
                        painter.setFont(font)
                        painter.drawText(i * 8, i * 12, w, h, Qt.AlignmentFlag.AlignCenter, "⏳ Loading\nFolder...")
                        
                painter.end()
                item.setIcon(QIcon(pixmap))
                self.grid_list.addItem(item)
                
                self.grid_folder_map[dir_path] = item
                folders_to_load.append(dir_path)

            # --- 2. DRAW COMIC FILES ---
            for full_path in comic_files:
                filename_only = os.path.splitext(os.path.basename(full_path))[0]
                item = QListWidgetItem(filename_only)
                item.setData(Qt.ItemDataRole.UserRole, full_path)
                self.grid_list.addItem(item)
                self.grid_items_map[full_path] = item

            # --- 3. DRAW CBL READING LIST FILES ---
            for full_path in cbl_files:
                filename_only = os.path.splitext(os.path.basename(full_path))[0]
                item = QListWidgetItem(f"📋 {filename_only}")
                item.setData(Qt.ItemDataRole.UserRole, f"CBL:{full_path}")
                item.setForeground(QColor('#ffb86c'))
                item.setIcon(self._make_cbl_icon(full_path))
                self.grid_list.addItem(item)

        except PermissionError: pass 
        
        # --- UPDATE NAVIGATION UI ---
        
        if hasattr(self, 'grid_up_btn'):
            self.grid_up_btn.show()
            parent_dir = os.path.dirname(self.current_grid_folder)
            self.grid_up_btn.setEnabled(parent_dir != self.current_grid_folder and os.path.exists(parent_dir))
            
            self.grid_fwd_btn.show()
            self.grid_fwd_btn.setEnabled(bool(getattr(self, 'forward_grid_folder', None) and os.path.exists(self.forward_grid_folder)))
            
            self.grid_title_label.setText(f"📂 {os.path.basename(self.current_grid_folder) or self.current_grid_folder}")
            self.grid_title_label.show()
        # ----------------------------

        self.grid_list.setUpdatesEnabled(True)

        if comic_files:
            self.cover_thread = CoverLoaderThread(comic_files)
            self.cover_thread.cover_loaded.connect(self.update_grid_icon)
            self.cover_thread.start()
            
        if folders_to_load:
            self.folder_cover_thread = FolderCoverLoaderThread(folders_to_load)
            self.folder_cover_thread.folder_cover_loaded.connect(self.update_folder_icon)
            self.folder_cover_thread.start()
            
    def update_folder_icon(self, folder_path, covers_bytes_list):

        # Cache the bytes so the size slider can re-render later
        if not hasattr(self, '_folder_bytes_cache'):
            self._folder_bytes_cache = {}
        if covers_bytes_list:
            self._folder_bytes_cache[os.path.normpath(folder_path)] = covers_bytes_list

        if folder_path in getattr(self, 'grid_folder_map', {}):
            item = self.grid_folder_map[folder_path]
            try:
                _ = item.text()
            except RuntimeError:
                return

            # Match the current grid size setting
            gs  = APP_SETTINGS.get('grid_size', 180)
            gh  = int(gs * 1.5)
            # Individual cover tiles inside the stack — slightly smaller than the cell
            w   = int(gs * 0.78)
            h   = int(gh * 0.78)
            # Offset step scales proportionally with icon size
            step_x = max(4, gs // 22)
            step_y = max(6, gh // 22)

            pixmap = QPixmap(gs, gh)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            colors = ["#21222c", "#282a36", "#44475a", "#6272a4", "#8be9fd"]

            visual_stack = [covers_bytes_list[i] if i < len(covers_bytes_list) else None for i in range(5)]
            visual_stack.reverse()

            for i in range(5):
                x = i * step_x
                y = i * step_y
                layer_data = visual_stack[i]
                if layer_data:
                    temp_pix = QPixmap()
                    if temp_pix.loadFromData(layer_data):
                        scaled = temp_pix.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation)
                        painter.drawPixmap(x, y, scaled)
                        painter.setPen(QColor("#1e1f29"))
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawRect(x, y, w, h)
                else:
                    painter.setBrush(QColor(colors[i]))
                    painter.setPen(QColor("#f8f8f2") if i == 4 else QColor("#1e1f29"))
                    painter.drawRect(x, y, w, h)

            painter.end()
            try:
                item.setIcon(QIcon(pixmap))
            except RuntimeError:
                pass
    
    def refresh_current_cbl(self):
        if hasattr(self, 'current_cbl_path') and self.current_cbl_path:
            self.load_cbl_grid(self.current_cbl_path, force_refresh=True)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Your Comics!")
        self.resize(1300, 850)

        self.hidden_file = "hidden_items.json"
        self.hidden_paths = set()
        if os.path.exists(self.hidden_file):
            try:
                with open(self.hidden_file, 'r') as f:
                    self.hidden_paths = set(json.load(f))
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
        self.current_comic_path = None
        self._current_xml_str   = None
        self._cover_size = 500  # fixed at max — no slider
        self.libraries_file = "libraries.json"
        self.reading_file = "reading_list.json"
        self.reading_history = []
        
        self.cover_thread = None       
        self.grid_items_map = {}       

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)

        self.left_tabs = QTabWidget()
        self.left_tabs.setObjectName("left_tabs")

        self.browse_tab = QWidget()
        self.browse_layout = QVBoxLayout(self.browse_tab)
        self.browse_layout.setContentsMargins(5, 5, 5, 5)

        self.lib_label = QLabel("Libraries")
        self.lib_label.setStyleSheet("font-weight: bold; color: #8be9fd; padding-left: 5px;")
        
        self.lib_list = QListWidget()
        self.lib_list.setMaximumHeight(100) 
        self.lib_list.itemClicked.connect(self.on_library_clicked)

        self.btn_layout = QHBoxLayout()
        self.add_lib_btn = QPushButton("+ Add Folder")
        self.remove_lib_btn = QPushButton("- Remove")
        self.all_drives_btn = QPushButton("Show All Drives")
        self.clear_cache_btn = QPushButton("Clear Cache")
        self.clear_cache_btn.clicked.connect(self.clear_image_cache)
        # And add it to the layout below:
        self.btn_layout.addWidget(self.clear_cache_btn)
        
        self.add_lib_btn.clicked.connect(self.add_to_libraries)
        self.remove_lib_btn.clicked.connect(self.remove_library)
        self.all_drives_btn.clicked.connect(self.show_all_drives)

        self.btn_layout.addWidget(self.add_lib_btn)
        self.btn_layout.addWidget(self.remove_lib_btn)
        self.btn_layout.addWidget(self.all_drives_btn)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Filter view, or press Enter for Deep Search...")
        self.search_bar.textChanged.connect(self.on_search_changed)
        self.search_bar.returnPressed.connect(self.perform_global_search) # <-- NEW TRIGGER

        # 1. Setup the File System Model (This feeds the Tree!)
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        
        # 2. Tell it to see comics AND our new .cbl Reading Lists!
        self.model.setNameFilters(["*.cbz", "*.cbr", "*.cb7", "*.pdf", "*.cbl"])
        self.model.setNameFilterDisables(False)

        # 1. Create the Tree View FIRST
        self.tree = QTreeView()
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_tree_right_click)

        # 2. Create the Proxy
        self.proxy_model = NaturalSortProxyModel()
        self.proxy_model.hidden_paths = self.hidden_paths
        
        # 3. Give your original model (self.model) to the Proxy
        self.proxy_model.setSourceModel(self.model)
        
        # 4. Give the Proxy to the Tree View (self.tree)
        self.tree.setModel(self.proxy_model)
        
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder) # <-- Force it to count UP!

        # 6. Apply your UI settings to the tree
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.selectionModel().selectionChanged.connect(self.on_file_selected)

        self.browse_layout.addWidget(self.lib_label)
        self.browse_layout.addWidget(self.lib_list)
        self.browse_layout.addLayout(self.btn_layout)
        self.browse_layout.addWidget(self.search_bar)
        self.browse_layout.addWidget(self.tree)

        self.reading_tab = QWidget()
        self.reading_layout = QVBoxLayout(self.reading_tab)
        self.reading_layout.setContentsMargins(5, 5, 5, 5)

        self.reading_list_widget = QListWidget()
        self.reading_list_widget.setViewMode(QListWidget.ViewMode.ListMode)
        self.reading_list_widget.setIconSize(QSize(50, 75))
        self.reading_list_widget.setWordWrap(True)
        self.reading_list_widget.itemClicked.connect(self.on_reading_item_clicked)
        
        # NEW: Context Menu setup for the Reading List
        self.reading_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.reading_list_widget.customContextMenuRequested.connect(self.show_reading_context_menu)
        
        self.reading_btn_layout = QHBoxLayout()
        self.remove_single_read_btn = QPushButton("❌ Remove Selected")
        self.remove_single_read_btn.clicked.connect(self.remove_selected_reading)
        
        self.clear_read_btn = QPushButton("🗑️ Clear All")
        self.clear_read_btn.clicked.connect(self.clear_reading_history)

        self.reading_btn_layout.addWidget(self.remove_single_read_btn)
        self.reading_btn_layout.addWidget(self.clear_read_btn)

        self.reading_layout.addWidget(self.reading_list_widget)
        self.reading_layout.addLayout(self.reading_btn_layout)

        self.left_tabs.addTab(self.browse_tab, "Library")
        self.left_tabs.addTab(self.reading_tab, "Reading")
        self.left_layout.addWidget(self.left_tabs)

        self.tabs = QTabWidget()
        
        # ==========================================
        # TAB 1: COMIC DETAILS  (side-by-side layout)
        # ==========================================
        self.details_tab = QWidget()
        self.details_layout = QVBoxLayout(self.details_tab)
        self.details_layout.setContentsMargins(6, 6, 6, 6)
        self.details_layout.setSpacing(6)

        # ── Top: cover (left) + info (right) side by side ──
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setChildrenCollapsible(False)

        # Left pane — cover image
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.cover_label = QLabel("Select a comic\nto view details")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setMinimumWidth(260)
        self.cover_label.setStyleSheet("color: #6272a4;")
        left_layout.addWidget(self.cover_label, 1)

        # Right pane — info box + More Info button
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        self.info_box = QTextBrowser()
        self.info_box.setStyleSheet("background-color: #21222c; color: #f8f8f2; padding: 10px; border-radius: 5px;")
        right_layout.addWidget(self.info_box, 1)

        more_info_row = QHBoxLayout()
        more_info_row.addStretch()
        self.more_info_btn = QPushButton("🔍 More Info / Edit")
        self.more_info_btn.setMinimumHeight(28)
        self.more_info_btn.setStyleSheet("background-color: #44475a; color: #f8f8f2; font-weight: bold; padding: 3px 10px; border-radius: 3px;")
        self.more_info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_info_btn.setEnabled(False)
        self.more_info_btn.clicked.connect(self.show_metadata_dialog)
        more_info_row.addWidget(self.more_info_btn)
        right_layout.addLayout(more_info_row)

        content_splitter.addWidget(left_pane)
        content_splitter.addWidget(right_pane)
        content_splitter.setSizes([340, 260])
        self.details_layout.addWidget(content_splitter, 1)

        # ── Navigation row: << | ◄ Prev | ✨ AI Chat | Next ► | >> ──
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(4)

        self.prev_folder_btn = QPushButton("«")
        self.prev_folder_btn.setMinimumHeight(35)
        self.prev_folder_btn.setFixedWidth(38)
        self.prev_folder_btn.setToolTip("Previous Folder")
        self.prev_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_folder_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.prev_folder_btn.clicked.connect(self.prev_folder)

        self.prev_btn = QPushButton("◄ Prev")
        self.prev_btn.setMinimumHeight(35)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.clicked.connect(self.prev_local_comic)

        self.ai_info_btn = QPushButton("✨ AI Chat")
        self.ai_info_btn.setMinimumHeight(35)
        self.ai_info_btn.setStyleSheet("background-color: #bd93f9; color: #282a36; font-weight: bold;")
        self.ai_info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ai_info_btn.clicked.connect(self.fetch_ai_info)

        self.next_btn = QPushButton("Next ►")
        self.next_btn.setMinimumHeight(35)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(self.next_local_comic)

        self.next_folder_btn = QPushButton("»")
        self.next_folder_btn.setMinimumHeight(35)
        self.next_folder_btn.setFixedWidth(38)
        self.next_folder_btn.setToolTip("Next Folder")
        self.next_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_folder_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.next_folder_btn.clicked.connect(self.next_folder)

        nav_layout.addWidget(self.prev_folder_btn)
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.ai_info_btn)
        nav_layout.addWidget(self.next_btn)
        nav_layout.addWidget(self.next_folder_btn)
        self.details_layout.addLayout(nav_layout)

        # ── Action buttons ──
        self.action_btn = QPushButton("Convert/Tag CBR and Tag CBZ")
        self.action_btn.setMinimumHeight(40)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.clicked.connect(self.process_comic)
        self.details_layout.addWidget(self.action_btn)

        self.convert_progress = QProgressBar(self.details_tab)
        self.convert_progress.setValue(0)
        self.convert_progress.setTextVisible(True)
        self.convert_progress.setVisible(False)
        self.details_layout.addWidget(self.convert_progress)

        self.read_btn = QPushButton("Read Comic")
        self.read_btn.setMinimumHeight(45)
        self.read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.read_btn.clicked.connect(self.open_in_reader)
        self.details_layout.addWidget(self.read_btn)

        self.grid_tab = QWidget()
        self.grid_layout = QVBoxLayout(self.grid_tab)
        
        self.grid_top_layout = QHBoxLayout()
        
       # --- NEW NAV BUTTONS & TITLE ---
        self.grid_title_label = QLabel("📂 Local Grid")
        self.grid_title_label.setStyleSheet("color: #8be9fd; font-weight: bold; font-size: 16px;")
        
        self.grid_up_btn = QPushButton("🡄 Up")
        self.grid_up_btn.setStyleSheet("background-color: #44475a; color: white; font-weight: bold; padding: 5px 10px;")
        self.grid_up_btn.clicked.connect(self.grid_go_up)
        self.grid_up_btn.setEnabled(False) # Visible, but greyed out by default!
        
        self.grid_fwd_btn = QPushButton("🡆 Forward")
        self.grid_fwd_btn.setStyleSheet("background-color: #44475a; color: white; font-weight: bold; padding: 5px 10px;")
        self.grid_fwd_btn.clicked.connect(self.grid_go_forward)
        self.grid_fwd_btn.setEnabled(False) # Visible, but greyed out by default!
        # -------------------------------
        
        self.cbl_stats_label = QLabel("")
        self.cbl_stats_label.setStyleSheet("color: #8be9fd; font-weight: bold; font-size: 16px;")
        self.cbl_stats_label.hide() 
        
        self.refresh_cbl_btn = QPushButton("🔄 Refresh Active Reading List")
        self.refresh_cbl_btn.setStyleSheet("background-color: #ffb86c; color: #282a36; font-weight: bold; padding: 5px;")
        self.refresh_cbl_btn.clicked.connect(self.refresh_current_cbl)
        self.refresh_cbl_btn.hide() 
        
        self.grid_top_layout.addWidget(self.grid_title_label)
        self.grid_top_layout.addWidget(self.grid_up_btn)
        self.grid_top_layout.addWidget(self.grid_fwd_btn)
        self.grid_top_layout.addWidget(self.cbl_stats_label)
        self.grid_top_layout.addStretch() 
        self.grid_top_layout.addWidget(self.refresh_cbl_btn)
        self.grid_layout.addLayout(self.grid_top_layout)

        # 2. Create and add the grid list below it
        self.grid_list = HoverSummaryList()
        self.grid_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.grid_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid_list.setMovement(QListWidget.Movement.Static)
        self.grid_list.setIconSize(QSize(180, 270))
        
        # --- THE ALIGNMENT & TEXT FIX ---
        self.grid_list.setGridSize(QSize(220, 350))
        self.grid_list.setWordWrap(True)            # Allows long filenames to wrap underneath the cover
        
        # --- THE SCROLLING FIX ---
        # Switches from "Snap to Row" to "Smooth Pixel" scrolling so you never skip rows again!
        self.grid_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.grid_list.verticalScrollBar().setSingleStep(25) # Adjust this number (15-30) for your perfect scroll speed
        # --------------------------------
        
        self.grid_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid_list.itemDoubleClicked.connect(self.on_grid_item_clicked)
        self.grid_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid_list.customContextMenuRequested.connect(self.show_grid_context_menu)
        self.grid_layout.addWidget(self.grid_list)

        # Grid cover size slider
        grid_size_row = QHBoxLayout()
        grid_size_lbl = QLabel("🖼")
        grid_size_lbl.setFixedWidth(20)
        self.grid_size_label = QLabel("180")
        self.grid_size_label.setFixedWidth(30)
        self.grid_size_label.setStyleSheet("color: #6272a4; font-size: 11px;")
        self.grid_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.grid_size_slider.setRange(80, 360)
        self.grid_size_slider.setValue(APP_SETTINGS.get("grid_size", 180))
        self.grid_size_slider.setToolTip("Grid cover size")
        self.grid_size_slider.valueChanged.connect(self._on_grid_size_changed)
        grid_size_row.addWidget(grid_size_lbl)
        grid_size_row.addWidget(self.grid_size_slider)
        grid_size_row.addWidget(self.grid_size_label)
        self.grid_layout.addLayout(grid_size_row)
        # Apply saved size immediately so the grid launches at the right size
        _gs = APP_SETTINGS.get("grid_size", 180)
        self.grid_list.setIconSize(QSize(_gs, int(_gs * 1.5)))
        self.grid_list.setGridSize(QSize(_gs + 40, int(_gs * 1.5) + 50))
        self.grid_size_label.setText(str(_gs))

        # Heavy tabs are built lazily on first click — keeps startup fast.
        # Store Nones as placeholders; _ensure_tab_built() fills them in.
        self.finder_tab = None
        self.chat_tab = None
        self.tagger_tab = None
        self.list_maker_tab = None
        self.new_releases_tab = None
        self.settings_tab = None
        self.getcomics_tab = None

        # Add the two local tabs immediately (always visible on startup)
        self.tabs.addTab(self.details_tab, "Comic Details")
        self.tabs.addTab(self.grid_tab, "Local Grid")
        # Add placeholder widgets for the deferred tabs
        for label in ("Comic Finder", "Comic Chat", "Batch Tagger",
                      "GetComics", "List Maker", "New Releases", "Settings"):
            placeholder = QWidget()
            self.tabs.addTab(placeholder, label)

        # Wire up the lazy-builder
        self.tabs.currentChanged.connect(self._ensure_tab_built)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.tabs)
        self.splitter.setSizes([350, 950]) 
        self.shortcut_action = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.shortcut_action.activated.connect(self.process_comic)
        self.apply_dark_theme()
        self.load_libraries()
        self.load_reading_history()
        
        # --- NEW: Auto-Load First Library on Startup ---
        if self.lib_list.count() > 0:
            first_item = self.lib_list.item(0)
            self.lib_list.setCurrentItem(first_item)
            self.on_library_clicked(first_item) # Simulates a user clicking it!
        # -----------------------------------------------
        
    # Tab index map (matches the addTab order above)
    _TAB_FINDER      = 2
    _TAB_CHAT        = 3
    _TAB_TAGGER      = 4
    _TAB_GETCOMICS   = 5
    _TAB_LISTMAKER   = 6
    _TAB_NEWRELEASES = 7
    _TAB_SETTINGS    = 8

    def _ensure_tab_built(self, index):
        # Build a deferred tab the first time the user clicks it.
        # Block signals during removeTab/insertTab to prevent currentChanged cascade.
        if index == self._TAB_FINDER and self.finder_tab is None:
            self.finder_tab = ComicFinderTab()
            if self.chat_tab is not None:
                self.finder_tab.analysis_completed.connect(self.chat_tab.update_context)
            self.tabs.blockSignals(True)
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, self.finder_tab, 'Comic Finder')
            self.tabs.blockSignals(False)
            self.tabs.setCurrentIndex(index)

        elif index == self._TAB_CHAT and self.chat_tab is None:
            self.chat_tab = ComicChatTab()
            if self.finder_tab is not None:
                self.finder_tab.analysis_completed.connect(self.chat_tab.update_context)
            self.tabs.blockSignals(True)
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, self.chat_tab, 'Comic Chat')
            self.tabs.blockSignals(False)
            self.tabs.setCurrentIndex(index)

        elif index == self._TAB_TAGGER and self.tagger_tab is None:
            self.tagger_tab = BatchTaggerTab()
            self.tabs.blockSignals(True)
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, self.tagger_tab, 'Batch Tagger')
            self.tabs.blockSignals(False)
            self.tabs.setCurrentIndex(index)

        elif index == self._TAB_GETCOMICS and self.getcomics_tab is None:
            self.getcomics_tab = GetComicsTab()
            if self.new_releases_tab is not None:
                self.getcomics_tab.download_completed.connect(
                    self.new_releases_tab.mark_downloaded)
            self.tabs.blockSignals(True)
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, self.getcomics_tab, 'GetComics')
            self.tabs.blockSignals(False)
            self.tabs.setCurrentIndex(index)

        elif index == self._TAB_LISTMAKER and self.list_maker_tab is None:
            self.list_maker_tab = ListMakerTab(self.model)
            self.tabs.blockSignals(True)
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, self.list_maker_tab, 'List Maker')
            self.tabs.blockSignals(False)
            self.tabs.setCurrentIndex(index)

        elif index == self._TAB_NEWRELEASES and self.new_releases_tab is None:
            self.new_releases_tab = NewReleasesTab()
            self.new_releases_tab.open_url.connect(self._open_url_in_getcomics)
            self.tabs.blockSignals(True)
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, self.new_releases_tab, 'New Releases')
            self.tabs.blockSignals(False)
            self.tabs.setCurrentIndex(index)

        elif index == self._TAB_SETTINGS and self.settings_tab is None:
            self.settings_tab = SettingsTab()
            self.tabs.blockSignals(True)
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, self.settings_tab, 'Settings')
            self.tabs.blockSignals(False)
            self.tabs.setCurrentIndex(index)

    def _open_url_in_getcomics(self, url: str):
        """Build the GetComics tab if needed, switch to it, and navigate to url."""
        if self.getcomics_tab is None:
            self.getcomics_tab = GetComicsTab()
            if self.new_releases_tab is not None:
                self.getcomics_tab.download_completed.connect(
                    self.new_releases_tab.mark_downloaded)
            self.tabs.blockSignals(True)
            idx = self._TAB_GETCOMICS
            self.tabs.removeTab(idx)
            self.tabs.insertTab(idx, self.getcomics_tab, 'Getcomic.info')
            self.tabs.blockSignals(False)
        self.tabs.setCurrentWidget(self.getcomics_tab)
        self.getcomics_tab.set_origin_article_url(url)
        self.getcomics_tab.url_bar.setText(url)
        self.getcomics_tab.load_url()

    def fetch_ai_info(self):
        if not self.current_comic_path:
            return
            
        base_name = os.path.splitext(os.path.basename(self.current_comic_path))[0]
        
        # 1. Extract the year before we clean the title
        year_match = re.search(r'\((\d{4})\)', base_name)
        year_str = f" ({year_match.group(1)})" if year_match else ""
        
        # 2. Clean out all the messy brackets and tags
        clean_name = re.sub(r'\(.*?\)|\[.*?\]', '', base_name).strip()
        
        # 3. The Issue Parser
        match = re.search(r'^(.*?)\s*#\s*(\d+)', clean_name)
        if not match:
            match = re.search(r'^(.*?)\s+(\d+)\s*$', clean_name)
            
        if match and match.group(1).strip():
            series = match.group(1).strip()
            issue = f" #{int(match.group(2))}" 
        else:
            series = clean_name
            issue = ""
            
        # 4. --- THE NEW FIX: The Volume Eraser! ---
        # This deletes " V1", " Vol. 2", or " Volume 3" from the end of the series name
        series = re.sub(r'\s+(?:v|vol|volume)\.?\s*\d+$', '', series, flags=re.IGNORECASE).strip()
            
        # 5. Combine them all into the perfect title!
        final_search_name = f"{series}{issue}{year_str}".strip()

        # Switch to the Comic Chat tab
        self._ensure_tab_built(self._TAB_CHAT)
        self.tabs.setCurrentIndex(self._TAB_CHAT)

        # Inject it into the chat box and hit send!
        if hasattr(self.chat_tab, 'chat_input'):
            question = f"Can you give me a summary, background info, and details about the comic: {final_search_name}?"
            self.chat_tab.chat_input.setText(question)
            
            if hasattr(self.chat_tab, 'send_btn'):
                self.chat_tab.send_btn.click()
            elif hasattr(self.chat_tab, 'send_message'):
                self.chat_tab.send_message()

    def load_prev_comic(self):
        # Find exactly where we are in the left-panel tree
        current_index = self.tree.currentIndex()
        if current_index.isValid():
            # Grab the item directly above it and select it
            prev_idx = self.tree.indexAbove(current_index)
            if prev_idx.isValid():
                self.tree.setCurrentIndex(prev_idx)

    def load_next_comic(self):
        # Find exactly where we are in the left-panel tree
        current_index = self.tree.currentIndex()
        if current_index.isValid():
            # Grab the item directly below it and select it
            next_idx = self.tree.indexBelow(current_index)
            if next_idx.isValid():
                self.tree.setCurrentIndex(next_idx)

    # --- READING HISTORY LOGIC ---
    def load_reading_history(self):
        if os.path.exists(self.reading_file):
            try:
                with open(self.reading_file, 'r') as f:
                    self.reading_history = json.load(f)
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
        self.refresh_reading_ui()

    def save_reading_history(self):
        with open(self.reading_file, 'w') as f:
            json.dump(self.reading_history, f)

    def add_to_reading_list(self, path):
        norm_path = os.path.normpath(path)
        if norm_path in self.reading_history:
            self.reading_history.remove(norm_path)
        
        self.reading_history.insert(0, norm_path)
        self.save_reading_history()
        self.refresh_reading_ui()

    def remove_selected_reading(self):
        current_item = self.reading_list_widget.currentItem()
        if current_item:
            file_path = os.path.normpath(current_item.data(Qt.ItemDataRole.UserRole))
            if file_path in self.reading_history:
                self.reading_history.remove(file_path)
                self.save_reading_history()
                self.refresh_reading_ui()

    def show_reading_context_menu(self, pos):
        item = self.reading_list_widget.itemAt(pos)
        if item:
            menu = QMenu()
            menu.setStyleSheet("""
                QMenu { background-color: #282a36; color: #f8f8f2; border: 1px solid #44475a; } 
                QMenu::item:selected { background-color: #44475a; }
            """)
            remove_action = menu.addAction("❌ Remove from Reading List")
            action = menu.exec(self.reading_list_widget.mapToGlobal(pos))
            if action == remove_action:
                file_path = os.path.normpath(item.data(Qt.ItemDataRole.UserRole))
                if file_path in self.reading_history:
                    self.reading_history.remove(file_path)
                    self.save_reading_history()
                    self.refresh_reading_ui()

    def clear_reading_history(self):
        self.reading_history.clear()
        self.save_reading_history()
        self.refresh_reading_ui()

    def refresh_reading_ui(self):
        
        self.reading_list_widget.clear()
        for path in self.reading_history:
            if not os.path.exists(path):
                continue 
            
            norm_path = os.path.normpath(path)
            filename = os.path.splitext(os.path.basename(norm_path))[0]
            
            item = QListWidgetItem(filename)
            item.setData(Qt.ItemDataRole.UserRole, norm_path)
            
            file_hash = hashlib.md5(norm_path.encode('utf-8')).hexdigest()
            cache_path = os.path.join(CACHE_DIR, f"{file_hash}.jpg")
            custom_cache_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
            
            # Prioritize Custom Covers first!
            target_img = custom_cache_path if os.path.exists(custom_cache_path) else cache_path
            
            if os.path.exists(target_img):
                pixmap = QPixmap(target_img)
                scaled = pixmap.scaled(50, 75, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(scaled))
                
            elif norm_path.lower().endswith('.cbl'):
                # Draw a neon clipboard icon for reading lists that don't have custom covers!
                pixmap = QPixmap(50, 75)
                pixmap.fill(QColor("#44475a"))
                painter = QPainter(pixmap)
                painter.setPen(QColor("#8be9fd"))
                font = painter.font(); font.setPointSize(18)
                painter.setFont(font)
                painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "📋")
                painter.end()
                item.setIcon(QIcon(pixmap))
                
            self.reading_list_widget.addItem(item)

    def on_reading_item_clicked(self, item):
        file_path = os.path.normpath(item.data(Qt.ItemDataRole.UserRole))
        if file_path:
            # If it's a Reading List, open it in the Grid!
            if file_path.lower().endswith('.cbl'):
                self.tabs.setCurrentIndex(1) 
                self.load_cbl_grid(file_path)
                self.add_to_reading_list(file_path) # Bump it back to the top of history!
            # If it's a comic, open it in the Local Details tab!
            else:
                self.tabs.setCurrentIndex(0) 
                self.current_comic_path = file_path
                self.load_comic_data(file_path)

    # --- UNIVERSAL NAVIGATION LOGIC ---
    def get_current_comic_list(self):
        """Return naturally-sorted list of comic paths in the same folder as the current comic."""
        if not self.current_comic_path:
            return []

        current_norm = os.path.normpath(self.current_comic_path)

        # First try: use the grid if it's showing the same folder
        grid_paths = []
        for i in range(self.grid_list.count()):
            data = self.grid_list.item(i).data(Qt.ItemDataRole.UserRole)
            if data and isinstance(data, str) and not data.startswith("FOLDER:") and not data.startswith("MISSING:"):
                grid_paths.append(os.path.normpath(data))

        if current_norm in grid_paths:
            return grid_paths

        # Fallback: read the folder directly from disk
        directory = os.path.dirname(current_norm)
        try:
            all_files = os.listdir(directory)
            comics = [
                os.path.normpath(os.path.join(directory, f))
                for f in all_files
                if f.lower().endswith(('.cbz', '.cbr'))
            ]
            comics.sort(key=lambda p: [
                int(t) if t.isdigit() else t.lower()
                for t in re.split(r'(\d+)', os.path.basename(p))
            ])
            return comics
        except Exception as _e:
            log.warning("get_current_comic_list failed: %s", _e)
        return []

    def update_local_nav_buttons(self):
        if not hasattr(self, 'prev_btn') or not hasattr(self, 'next_btn'):
            return

        if not self.current_comic_path:
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            if hasattr(self, 'prev_folder_btn'): self.prev_folder_btn.setEnabled(False)
            if hasattr(self, 'next_folder_btn'): self.next_folder_btn.setEnabled(False)
            return

        current_norm = os.path.normpath(self.current_comic_path)
        paths = self.get_current_comic_list()

        if current_norm in paths:
            idx = paths.index(current_norm)
            self.prev_btn.setEnabled(idx > 0)
            self.next_btn.setEnabled(idx < len(paths) - 1)
        else:
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)

        # Update folder nav buttons
        if hasattr(self, 'prev_folder_btn') and hasattr(self, 'next_folder_btn'):
            folder = self._get_current_folder()
            if folder:
                all_folders = self._all_comic_folders()
                norm_folder = os.path.normpath(folder)
                if norm_folder in all_folders:
                    fidx = all_folders.index(norm_folder)
                    self.prev_folder_btn.setEnabled(fidx > 0)
                    self.next_folder_btn.setEnabled(fidx < len(all_folders) - 1)
                else:
                    self.prev_folder_btn.setEnabled(False)
                    self.next_folder_btn.setEnabled(False)
            else:
                self.prev_folder_btn.setEnabled(False)
                self.next_folder_btn.setEnabled(False)

    def _get_current_folder(self):
        """Return the folder containing the current comic, or None."""
        if not self.current_comic_path:
            return None
        return os.path.dirname(os.path.normpath(self.current_comic_path))

    @staticmethod
    def _nsk(path):
        """Natural-sort key on the basename of a path."""
        return [int(t) if t.isdigit() else t.lower()
                for t in re.split(r'(\d+)', os.path.basename(path))]

    def _all_comic_folders(self):
        """Return a flat list of every folder (at any depth) under the user's
        libraries that directly contains at least one comic file, in natural
        tree order (parent before children, siblings sorted naturally).
        Falls back to the parent of the current comic if no libraries configured."""
        roots = [self.lib_list.item(i).text() for i in range(self.lib_list.count())]
        if not roots and self.current_comic_path:
            roots = [os.path.dirname(os.path.normpath(self.current_comic_path))]

        folders = []
        seen = set()
        for root in roots:
            if not os.path.isdir(root):
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                # Sort subdirectories in-place so os.walk visits them naturally
                dirnames.sort(key=lambda d: [
                    int(t) if t.isdigit() else t.lower()
                    for t in re.split(r'(\d+)', d)
                ])
                has_comic = any(f.lower().endswith(('.cbz', '.cbr')) for f in filenames)
                if has_comic:
                    norm = os.path.normpath(dirpath)
                    if norm not in seen:
                        seen.add(norm)
                        folders.append(norm)
        # Do NOT re-sort here — os.walk already visits in the right tree order.
        return folders

    def _first_comic_in_folder(self, folder):
        """Return the first naturally-sorted comic file in a folder, or None."""
        try:
            files = [
                f for f in os.listdir(folder)
                if f.lower().endswith(('.cbz', '.cbr'))
            ]
            files.sort(key=lambda f: [
                int(t) if t.isdigit() else t.lower()
                for t in re.split(r'(\d+)', f)
            ])
            return os.path.normpath(os.path.join(folder, files[0])) if files else None
        except Exception as _e:
            log.warning("_first_comic_in_folder failed: %s", _e)
            return None

    def _navigate_to_comic(self, path):
        """Load a comic and sync the left-panel tree to it."""
        self.current_comic_path = path
        self.load_comic_data(path)
        tree_index = self.model.index(path)
        if tree_index.isValid():
            proxy_index = self.proxy_model.mapFromSource(tree_index)
            self.tree.setCurrentIndex(proxy_index)
            self.tree.scrollTo(proxy_index)

    def prev_folder(self):
        folder = self._get_current_folder()
        if not folder:
            return
        all_folders = self._all_comic_folders()
        norm = os.path.normpath(folder)
        if norm not in all_folders:
            return
        idx = all_folders.index(norm)
        if idx > 0:
            target = self._first_comic_in_folder(all_folders[idx - 1])
            if target:
                self._navigate_to_comic(target)

    def next_folder(self):
        folder = self._get_current_folder()
        if not folder:
            return
        all_folders = self._all_comic_folders()
        norm = os.path.normpath(folder)
        if norm not in all_folders:
            return
        idx = all_folders.index(norm)
        if idx < len(all_folders) - 1:
            target = self._first_comic_in_folder(all_folders[idx + 1])
            if target:
                self._navigate_to_comic(target)

    def prev_local_comic(self):
        current_norm = os.path.normpath(self.current_comic_path)
        paths = self.get_current_comic_list()
        if current_norm in paths:
            idx = paths.index(current_norm)
            if idx > 0:
                new_path = paths[idx - 1]
                self.current_comic_path = new_path
                self.load_comic_data(new_path)

    def next_local_comic(self):
        current_norm = os.path.normpath(self.current_comic_path)
        paths = self.get_current_comic_list()
        if current_norm in paths:
            idx = paths.index(current_norm)
            if idx < len(paths) - 1:
                new_path = paths[idx + 1]
                self.current_comic_path = new_path
                self.load_comic_data(new_path)

    def on_search_changed(self, text):
        # This handles the instant filtering of whatever you are currently looking at!
        query = text.lower()
        for i in range(self.grid_list.count()):
            item = self.grid_list.item(i)
            # Hide the item if the text doesn't match the search
            item.setHidden(query not in item.text().lower())
    
    def perform_global_search(self):
        query = self.search_bar.text().strip()
        if not query: return
        
        libraries = [self.lib_list.item(i).text() for i in range(self.lib_list.count())]
        if not libraries: return
        
        self.tabs.setCurrentIndex(1)
        self.grid_list.clear()
        self.grid_items_map.clear()
        self.grid_folder_map = getattr(self, 'grid_folder_map', {})
        self.grid_folder_map.clear()
        
        item = QListWidgetItem(f"🔍 Deep Searching {len(libraries)} libraries...")
        self.grid_list.addItem(item)
        
        self.main_search_thread = DeepSearchThread(query, libraries)
        self.main_search_thread.results_ready.connect(self.on_global_search_results)
        self.main_search_thread.start()

    def on_global_search_results(self, results):
        
        self.grid_list.clear()
        if not results:
            self.grid_list.addItem("❌ No matches found in your library.")
            return
            
        if hasattr(self, 'refresh_cbl_btn'): self.refresh_cbl_btn.hide()
        if hasattr(self, 'cbl_stats_label'): self.cbl_stats_label.hide()
            
        self.grid_list.setUpdatesEnabled(False)
        directory_items = []
        comic_files = []
        cbl_files = []
        
        for res in results:
            # --- THE HIDE FILTER ---
            if os.path.normpath(res['path']) in getattr(self, 'hidden_paths', set()):
                continue
            # -----------------------
            
            if res['is_folder']:
                directory_items.append((res['name'], res['path']))
            elif res['path'].lower().endswith('.cbl'):
                cbl_files.append(res['path'])
            else:
                comic_files.append(res['path'])
            
        # --- DRAW FOLDERS ---
        folders_to_load = []
        for dir_name, dir_path in directory_items:
            item = QListWidgetItem(dir_name)
            item.setData(Qt.ItemDataRole.UserRole, f"FOLDER:{dir_path}")
            
            pixmap = QPixmap(180, 270)
            pixmap.fill(Qt.GlobalColor.transparent) 
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            colors = ["#21222c", "#282a36", "#44475a", "#6272a4", "#8be9fd"]
            w, h = 140, 210 
            
            for i in range(5):
                painter.setBrush(QColor(colors[i]))
                painter.setPen(QColor("#f8f8f2") if i == 4 else QColor("#1e1f29"))
                painter.drawRect(i * 8, i * 12, w, h)
                if i == 4:
                    painter.setPen(QColor("#282a36"))
                    font = painter.font(); font.setBold(True); font.setPointSize(10)
                    painter.setFont(font)
                    painter.drawText(i * 8, i * 12, w, h, Qt.AlignmentFlag.AlignCenter, "⏳ Loading\nFolder...")
                    
            painter.end()
            item.setIcon(QIcon(pixmap))
            self.grid_list.addItem(item)
            
            self.grid_folder_map[dir_path] = item
            folders_to_load.append(dir_path)

        # --- DRAW COMIC FILES ---
        for full_path in comic_files:
            filename_only = os.path.splitext(os.path.basename(full_path))[0]
            item = QListWidgetItem(filename_only)
            item.setData(Qt.ItemDataRole.UserRole, full_path)
            self.grid_list.addItem(item)
            self.grid_items_map[full_path] = item

        # --- DRAW CBL FILES ---
        for full_path in cbl_files:
            filename_only = os.path.splitext(os.path.basename(full_path))[0]
            item = QListWidgetItem(f"📋 {filename_only}")
            item.setData(Qt.ItemDataRole.UserRole, f"CBL:{full_path}")
            item.setForeground(QColor('#ffb86c'))
            item.setIcon(self._make_cbl_icon(full_path))
            self.grid_list.addItem(item)
                
        self.grid_list.setUpdatesEnabled(True)

        if comic_files:
            self.cover_thread = CoverLoaderThread(comic_files)
            self.cover_thread.cover_loaded.connect(self.update_grid_icon)
            self.cover_thread.start()
            
        if folders_to_load:
            self.folder_cover_thread = FolderCoverLoaderThread(folders_to_load)
            self.folder_cover_thread.folder_cover_loaded.connect(self.update_folder_icon)
            self.folder_cover_thread.start()

    def load_libraries(self):
        if os.path.exists(self.libraries_file):
            try:
                with open(self.libraries_file, 'r') as f:
                    paths = json.load(f)
                    for path in paths:
                        self.lib_list.addItem(path)
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
    def save_libraries(self):
        paths = [self.lib_list.item(i).text() for i in range(self.lib_list.count())]
        with open(self.libraries_file, 'w') as f:
            json.dump(paths, f)

    def add_to_libraries(self):
        idx = self.tree.currentIndex()
        source_idx = self.proxy_model.mapToSource(idx) 
        if source_idx.isValid() and self.model.isDir(source_idx):
            path = self.model.filePath(source_idx)
            if path not in [self.lib_list.item(i).text() for i in range(self.lib_list.count())]:
                self.lib_list.addItem(path)
                self.save_libraries()

    def remove_library(self):
        current_item = self.lib_list.currentItem()
        if current_item:
            self.lib_list.takeItem(self.lib_list.row(current_item))
            self.save_libraries()

    def on_library_clicked(self, item):
        path = item.text()
        idx = self.model.index(path)
        proxy_idx = self.proxy_model.mapFromSource(idx) 
        self.tree.setRootIndex(proxy_idx)
        self.tabs.setCurrentIndex(1)
        self.load_folder_grid(path)
        self.current_comic_path = None
        self.action_btn.setEnabled(False)
        self.update_local_nav_buttons()

    def show_all_drives(self):
        idx = self.model.index("")
        proxy_idx = self.proxy_model.mapFromSource(idx)
        self.tree.setRootIndex(proxy_idx)

    def open_in_reader(self):
        if self.current_comic_path:
            self.add_to_reading_list(self.current_comic_path)
            # Pull the path dynamically from your settings!
            yac_path = APP_SETTINGS.get("reader_path", r"C:\Program Files\YACReader\YACReader.exe")
            try:
                subprocess.Popen([yac_path, self.current_comic_path])
            except FileNotFoundError:
                QMessageBox.warning(self, "Error", f"Could not find reader at:\n{yac_path}\n\nPlease update your path in Settings!")
                os.startfile(self.current_comic_path)

    def keyPressEvent(self, event):
        # Tree expansion logic
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.tree.hasFocus():
                index = self.tree.currentIndex()
                source_index = self.proxy_model.mapToSource(index)
                if source_index.isValid() and self.model.isDir(source_index):
                    self.tree.setExpanded(index, not self.tree.isExpanded(index))
        # NEW: Delete key logic for Reading List
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.reading_list_widget.hasFocus():
                self.remove_selected_reading()
                
        super().keyPressEvent(event)
    def on_file_selected(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes: return
        
        source_index = self.proxy_model.mapToSource(indexes[0])
        
        file_path = os.path.normpath(self.model.filePath(source_index))
        file_info = self.model.fileInfo(source_index)
        
        # 1. If it's a folder, load the Grid!
        if file_info.isDir():
            self.tabs.setCurrentIndex(1)
            self.load_folder_grid(file_path)
            self.current_comic_path = None
            self.action_btn.setEnabled(False)
            self.update_local_nav_buttons()
            return

        # --- 2. THE NEW PHASE 1 FIX: INTERCEPT .CBL FILES! ---
        if file_path.lower().endswith('.cbl'):
            self.tabs.setCurrentIndex(1) # Instantly switch to the Grid Tab!
            self.load_cbl_grid(file_path) # Send the file to our new generator!
            self.add_to_reading_list(file_path) # <--- NEW: Automatically add it to History!
            self.current_comic_path = None
            self.action_btn.setEnabled(False)
            self.update_local_nav_buttons()
            return
        # -----------------------------------------------------

        # 3. If it's a CBZ/CBR, load the Comic Details tab!
        self.tabs.setCurrentIndex(0) 
        if file_path.lower().endswith(('.cbz', '.cbr')):
            self.current_comic_path = file_path 
            if file_path.lower().endswith('.cbr') and not HAS_RAR:
                self.cover_label.clear()
                self.info_box.setHtml("<h3 style='color: #ff5555;'>Error: 'rarfile' missing</h3>")
                self.action_btn.setEnabled(False)
                self.update_local_nav_buttons()
                return
            self.load_comic_data(file_path)
        else:
            self.current_comic_path = None
            self.action_btn.setEnabled(False)
            self.update_local_nav_buttons()
    
    def on_grid_item_clicked(self, item):

        # --- THE CTRL-CLICK BYPASS ---
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier or modifiers & Qt.KeyboardModifier.ShiftModifier:
            return 
        # -----------------------------

        user_data = item.data(Qt.ItemDataRole.UserRole)
        if not user_data: return
        
        user_str = str(user_data)
        
        # --- PHASE 0: CBL READING LIST ---
        if user_str.startswith("CBL:"):
            cbl_path = user_str[4:]
            if os.path.exists(cbl_path):
                self.tabs.setCurrentIndex(1)  # switch to Local Grid tab
                self.load_cbl_grid(cbl_path)
            return

        # --- PHASE 1: FOLDER NAVIGATION! ---
        if user_str.startswith("FOLDER:"):
            folder_path = user_str.split("FOLDER:")[1]
            if os.path.exists(folder_path):
                # 1. Reload the grid with the contents of the new folder!
                self.load_folder_grid(folder_path)
                
                # 2. Sync the left-panel Tree so it highlights the folder you just entered!
                source_idx = self.model.index(folder_path)
                if source_idx.isValid():
                    proxy_idx = self.proxy_model.mapFromSource(source_idx)
                    self.tree.setCurrentIndex(proxy_idx)
                    self.tree.setExpanded(proxy_idx, True)
            return

        # --- PHASE 2: Check if it's a MISSING comic in a CBL! ---
        if user_str.startswith("MISSING:"):
            raw_query = user_str.split("MISSING:")[1]
            
            # THE FIX: Safely chop off the year (e.g., "1999" or "2015") if it is at the end of the string!
            search_query = re.sub(r'\s+(19|20)\d{2}$', '', raw_query).strip()
            
            getcomics_idx = self.tabs.indexOf(self.getcomics_tab)
            if getcomics_idx != -1:
                self.tabs.setCurrentIndex(getcomics_idx)
                
                safe_query = urllib.parse.quote_plus(search_query)
                search_url = f"https://getcomics.org/?s={safe_query}"
                
                self._ensure_tab_built(self._TAB_GETCOMICS)
                self.getcomics_tab.url_bar.setText(search_url)
                self.getcomics_tab.load_url()
            return
            
        # --- PHASE 3: Normal logic for opening Owned comics ---
        file_path = os.path.normpath(user_str)
        if os.path.exists(file_path):
            self.tabs.setCurrentIndex(0) 
            self.current_comic_path = file_path
            self.load_comic_data(file_path)
            

    def process_comic(self):
        if not self.current_comic_path: return
        
        # BULLETPROOF LOCK: If the button is already greyed out, ignore the click!
        if not self.action_btn.isEnabled(): 
            return
            
        self.action_btn.setEnabled(False)
        
        dialog = MetadataMatchDialog(self.current_comic_path, self.cover_label.pixmap())
        if dialog.exec():
            # If you clicked Inject, start the conversion!
            if hasattr(dialog, 'xml_string') and dialog.xml_string:
                self.start_conversion(dialog.xml_string)
            else:
                self.action_btn.setEnabled(True) # Unlock if data was missing
        else:
            self.action_btn.setEnabled(True) # Unlock if you clicked X or Cancel

    def start_conversion(self, xml_string):
        filename = os.path.basename(self.current_comic_path)
        self.action_btn.setText("Starting conversion...")
        self.convert_progress.setVisible(True)
        self.convert_progress.setValue(0)
        self.info_box.setHtml(f"<h3 style='color: #8be9fd;'>Extracting, Tagging, and Zipping {filename}...</h3>")
        
        self.conversion_thread = ComicConverterThread(self.current_comic_path, xml_string)
        self.conversion_thread.progress_update.connect(self.update_convert_progress)
        self.conversion_thread.status_update.connect(self.update_convert_status)
        self.conversion_thread.finished_conversion.connect(self.on_conversion_complete)
        self.conversion_thread.start()

    def update_convert_progress(self, current, total):
        if total > 0:
            percentage = int((current / total) * 100)
            self.convert_progress.setValue(percentage)

    def update_convert_status(self, msg):
        self.action_btn.setText(msg)

    def on_conversion_complete(self, success, message, new_path):
        # 1. Reset the UI immediately
        self.convert_progress.setVisible(False) 
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Convert/Tag CBR and Tag CBZ")
        
        # 2. Process the file
        if success:
            old_path = self.current_comic_path
            self.current_comic_path = new_path
            
            # If a CBR became a CBZ, refresh the grid!
            if old_path and old_path != new_path:
                folder_path = os.path.dirname(new_path)
                self.load_folder_grid(folder_path)
                
            self.load_comic_data(new_path)
            self.info_box.append(f"<h3 style='color: #50fa7b;'>{message}</h3>")
        else:
            self.info_box.setHtml(f"<h3 style='color: #ff5555;'>{message}</h3>")

    # --- NEW PROGRESS HANDLERS ---
    def update_convert_progress(self, current, total):
        if total > 0:
            percentage = int((current / total) * 100)
            self.convert_progress.setValue(percentage)

    def update_convert_status(self, msg):
        self.action_btn.setText(msg)
    # -----------------------------

    def on_conversion_complete(self, success, message, new_path):
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Convert/Tag CBR and Tag CBZ")
        self.convert_progress.setVisible(False) # Hide progress bar when done
        
        if success:
            self.current_comic_path = new_path
            self.load_comic_data(new_path)
            self.info_box.append(f"<h3 style='color: #50fa7b;'>{message}</h3>")
        else:
            self.info_box.setHtml(f"<h3 style='color: #ff5555;'>{message}</h3>")
        
        # We need to construct the XML string here to pass to the thread
        # For now, it uses a generic string, but you can plug your Gemini summary in here!
        xml_string = f"""<?xml version="1.0" encoding="utf-8"?>
        <ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
          <Title>{os.path.splitext(filename)[0]}</Title>
          <Summary>Summary goes here.</Summary>
        </ComicInfo>"""

        self.conversion_thread = ComicConverterThread(self.current_comic_path, xml_string)
        self.conversion_thread.finished_conversion.connect(self.on_conversion_complete)
        self.conversion_thread.start()

    def on_conversion_complete(self, success, message, new_path):
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Convert/Tag CBR and Tag CBZ")
        
        if success:
            self.current_comic_path = new_path
            self.load_comic_data(new_path)
            self.info_box.append(f"<h3 style='color: #50fa7b;'>{message}</h3>")
        else:
            self.info_box.setHtml(f"<h3 style='color: #ff5555;'>{message}</h3>")

    def clear_image_cache(self):
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR, exist_ok=True)
            self.info_box.setHtml("<h3 style='color: #ff5555;'>Image cache cleared!</h3>")        
    
    def refresh_current_cbl(self):
        if hasattr(self, 'current_cbl_path') and self.current_cbl_path:
            # Force the grid to ignore the cache and rescan your hard drive
            self.load_cbl_grid(self.current_cbl_path, force_refresh=True)
            
    def load_cbl_grid(self, cbl_path, force_refresh=False):
        self.grid_list.clear()
        self.grid_items_map.clear()
        self.current_cbl_path = cbl_path
        
        if hasattr(self, 'refresh_cbl_btn'):
            self.refresh_cbl_btn.show()
            
        # Hide the folder navigation when viewing a reading list!
        if hasattr(self, 'grid_up_btn'):
            self.grid_up_btn.hide()
            self.grid_fwd_btn.hide()
            self.grid_title_label.setText(f"📋 {os.path.basename(cbl_path)}")
            self.grid_title_label.show()
            
        if getattr(self, 'cover_thread', None) and self.cover_thread.isRunning():
            self.cover_thread.stop()
            self.cover_thread.wait()

        self.grid_list.setUpdatesEnabled(False)

        try:
            tree = ET.parse(cbl_path)
            root = tree.getroot()

            cache_file = "cbl_match_cache.json"
            cache_data = {}
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                except Exception as _e:
                    log.warning("Suppressed exception: %s", _e)
            cbl_mtime = os.path.getmtime(cbl_path) if os.path.exists(cbl_path) else 0
            matches_to_draw = []

            if not force_refresh and cbl_path in cache_data and cache_data[cbl_path].get('mtime') == cbl_mtime:
                print("⚡ Loading CBL from Lightning Cache!")
                matches_to_draw = cache_data[cbl_path]['matches']
            else:
                print("⏳ Scanning Library for CBL Matches (This will be cached)...")
                search_folders = [self.lib_list.item(i).text() for i in range(self.lib_list.count())]
                if os.path.dirname(cbl_path) not in search_folders:
                    search_folders.append(os.path.dirname(cbl_path))

                local_inventory = []
                scan_count = 0
                for folder in search_folders:
                    if not os.path.exists(folder): continue 
                    for dirpath, _, filenames in os.walk(folder):
                        for f in filenames:
                            scan_count += 1
                            if scan_count % 100 == 0: QApplication.processEvents()
                                
                            if f.lower().endswith(('.cbz', '.cbr')):
                                full_path = os.path.normpath(os.path.join(dirpath, f))
                                base_name = os.path.splitext(f)[0]

                                # --- 1. EXTRACT YEAR SAFELY (Only from brackets/parentheses!) ---
                                # This prevents grabbing the "1994" out of Novus cover dates like "1994-05-00", which prevents unfair year penalties!
                                y_match = re.search(r'[\[\(](19\d{2}|20\d{2})[\]\)]', base_name)
                                f_year = y_match.group(1) if y_match else ""
                                
                                # --- 2. PRE-CLEAN MESSY NOVUS FORMATS ---
                                # Translates URL Hex codes back into normal punctuation!
                                pre_clean = base_name.replace('_2C', ',').replace('_2c', ',')
                                
                                # Strip exact release dates embedded in titles (e.g. "1993-01-00")
                                pre_clean = re.sub(r'\b(19|20)\d{2}[-\.]\d{2}[-\.]\d{2}\b', '', pre_clean)
                                
                                # Strip reading order prefixes (e.g. "002 ", "15. ", "07 - ")
                                pre_clean = re.sub(r'^(?:0\d{1,3}[\.\-]?|\d{1,4}[\.\-])\s+', '', pre_clean)
                                
                                # --- 3. CATCH HIDDEN ISSUES ---
                                # Finds issue numbers hidden inside parentheses before we delete them! (e.g. "(_02)" or "(#01)" or "( 07)")
                                m_novus = re.search(r'\(\s*[#_]?\s*0*(\d{1,3}[a-zA-Z]?)\s*\)', pre_clean)
                                
                                # --- 4. FINAL CLEANUP ---
                                clean_name = re.sub(r'\(.*?\)|\[.*?\]', '', pre_clean).strip()
                                clean_name = re.sub(r'[,–—:-]+\s*$', '', clean_name).strip() 
                                
                                # --- THE BULLETPROOF FAST SCANNER ---
                                # ADDED UNDERSCORE TO HASH MATCHER to perfectly catch "Outsiders _010"
                                m_hash = re.search(r'[#_]\s*0*(\d+[a-zA-Z]?)', clean_name)
                                m_vol_and_iss = re.search(r'(?i)\b(?:v|vol|volume)\.?\s*\d+(?:\s*[-–—:]\s*|\s+)0*(\d+[a-zA-Z]?)', clean_name)
                                m_vol = re.search(r'(?i)\b(?:v|vol|volume|book|bk|tpb)\.?\s*0*(\d+[a-zA-Z]?)', clean_name)
                                m_dash = re.search(r'\b0*(\d+[a-zA-Z]?)\s*[-–—:]', clean_name)
                                m_end = re.search(r'\b0*(\d+[a-zA-Z]?)$', clean_name)
                                m_trap = re.search(r'\s+0*(\d+[a-zA-Z]?)\b', clean_name)
                                
                                f_issue = ""
                                f_series = clean_name
                                
                                if m_novus:
                                    f_issue = m_novus.group(1).lstrip('0') or "0"
                                    mv = re.search(r'(?i)\b(?:v|vol|volume)\.?\s*\d+', clean_name)
                                    if mv: f_series = clean_name[:mv.start()].strip()
                                elif m_hash:
                                    f_issue = m_hash.group(1).lstrip('0') or "0"
                                    cut = m_hash.start()
                                    mv = re.search(r'(?i)\b(?:v|vol|volume)\.?\s*\d+', clean_name)
                                    if mv and mv.start() < cut: cut = mv.start()
                                    f_series = clean_name[:cut].strip()
                                elif m_vol_and_iss:
                                    f_issue = m_vol_and_iss.group(1).lstrip('0') or "0"
                                    mv_start = re.search(r'(?i)\b(?:v|vol|volume)\.?\s*\d+', clean_name).start()
                                    f_series = (clean_name[:mv_start] + " " + clean_name[m_vol_and_iss.end():]).strip()
                                elif m_vol:
                                    f_issue = m_vol.group(1).lstrip('0') or "0"
                                    f_series = (clean_name[:m_vol.start()] + " " + clean_name[m_vol.end():]).strip()
                                elif m_dash:
                                    f_issue = m_dash.group(1).lstrip('0') or "0"
                                    f_series = clean_name[:m_dash.start()].strip()
                                elif m_end:
                                    f_issue = m_end.group(1).lstrip('0') or "0"
                                    f_series = clean_name[:m_end.start()].strip()
                                elif m_trap and m_trap.group(1) not in ['2099', '1602', '3000']:
                                    f_issue = m_trap.group(1).lstrip('0') or "0"
                                    f_series = clean_name[:m_trap.start()].strip()
                                    
                                local_inventory.append({
                                    'path': full_path, 'series': f_series.lower(), 'issue': f_issue, 'year': f_year
                                })

                def clean_for_match(text):
                                    t = str(text).lower().replace('&', 'and')
                                    t = t.replace('_', ' ') # THE UNDERSCORE FIX: Prevents words from mashing together!
                                    t = t.replace("'", "").replace("’", "")
                                    t = t.replace("maxx", "max") 
                                    
                                    # THE 2099 FIX: Only strip years explicitly inside parentheses
                                    t = re.sub(r'\(\s*(19|20)\d{2}\s*\)', '', t) 
                                    
                                    # THE READING ORDER FIX: Strip list numbers like "07. " or "012 - " from the start!
                                    # (Safely ignores actual titles like "100 Bullets" because they have no dot/dash)
                                    t = re.sub(r'^\d+[\.\-]\s*', '', t)
                                    t = re.sub(r'^0\d*\s+', '', t) # Strips raw numbers if they start with a 0 (e.g. "07 ")
                                    
                                    t = re.sub(r'[-–—:()\[\]]', ' ', t) 
                                    t = re.sub(r'[^a-z0-9\s]', '', t)
                                    t = re.sub(r'^(frank castles|frank castle|marvels|marvel|dc universe|dc comics|dc)\s+', '', t)
                                    return " ".join(re.sub(r'\b(the|of|a|an)\b', '', t).split())
                    
                def get_core_title(text):
                    t = re.sub(r'\b(volume|vol|v|book|bk|part|pt|tpb|trade paperback|edition|collection|epic|masterwork|masterworks|omnibus|compendium)\b\s*\d*', '', text)
                    return " ".join(t.split())

                all_books = root.findall('.//Book')
                for idx, book in enumerate(all_books):
                    if idx % 10 == 0: QApplication.processEvents()
                        
                    c_series = book.get('Series', '')
                    c_num_raw = book.get('Number', '').strip()
                    c_year = book.get('Year', '').strip()

                    num_match = re.search(r'(\d+[a-zA-Z]?)', c_num_raw)
                    c_num = num_match.group(1).lstrip('0') or "0" if num_match else ""

                    if c_num == "":
                        c_m_vol = re.search(r'(?i)\b(?:v|vol|volume|book|bk|tpb)\.?\s*(\d+[a-zA-Z]?)\b', c_series)
                        if c_m_vol:
                            c_num = c_m_vol.group(1).lstrip('0') or "0"
                            c_series = c_series[:c_m_vol.start()].strip()
                        else:
                            end_num_match = re.search(r'\s+(\d+[a-zA-Z]?)$', c_series)
                            if end_num_match:
                                c_num = end_num_match.group(1).lstrip('0') or "0"
                                c_series = c_series[:end_num_match.start()].strip()

                    display_num = c_num_raw if c_num_raw else c_num
                    display_name = f"{c_series} #{display_num}" if display_num else c_series
                    if c_year: display_name += f"\n({c_year})"

                    c_clean = clean_for_match(c_series)
                    c_core = get_core_title(c_clean)
                    
                    c_is_epic = "epic" in c_clean
                    c_is_mw = "masterwork" in c_clean
                    c_is_omni = "omnibus" in c_clean
                    c_is_comp = "compendium" in c_clean
                    
                    found_path = None
                    best_score = -999
                    
                    # Track if the CBL issue number is actually a year (for One-Shot bypass)
                    c_num_digits = re.sub(r'\D', '', c_num)
                    c_iss_is_year = c_num_digits.isdigit() and 1900 <= int(c_num_digits) <= 2100
                    
                    for comic in local_inventory:
                        f_num = comic['issue']
                        f_num_digits = re.sub(r'\D', '', f_num)
                        f_iss_is_year = f_num_digits.isdigit() and 1900 <= int(f_num_digits) <= 2100
                        
                        issue_match = False
                        
                        # THE 146b FIX: Compare just the digits so '146' matches '146b'
                        if c_num_digits and f_num_digits and c_num_digits == f_num_digits:
                            issue_match = True
                        elif c_num == "" and f_num == "":
                            issue_match = True
                        # THE ONE-SHOT FIX: Green Lantern #1 == Green Lantern 2005
                        elif (c_num_digits == "1" and f_iss_is_year) or (f_num_digits == "1" and c_iss_is_year):
                            issue_match = True 
                        elif c_num == "":
                            issue_match = True
                            
                        if not issue_match: continue

                        f_clean = clean_for_match(comic['series'])
                        f_core = get_core_title(f_clean)

                        # --- DOUBLE SHIELD 1: TPB/Collection Formatting ---
                        f_is_epic = "epic" in f_clean
                        f_is_mw = "masterwork" in f_clean
                        f_is_omni = "omnibus" in f_clean
                        f_is_comp = "compendium" in f_clean
                        f_is_tpb = bool(re.search(r'\b(tpb|trade paperback)\b', f_clean))
                        
                        c_is_epic = "epic" in c_clean
                        c_is_mw = "masterwork" in c_clean
                        c_is_omni = "omnibus" in c_clean
                        c_is_comp = "compendium" in c_clean
                        c_is_tpb = bool(re.search(r'\b(tpb|trade paperback)\b', c_clean))

                        # Hard format boundaries! Singles can't steal TPBs, TPBs can't steal Singles!
                        if c_is_epic and not f_is_epic: continue
                        if f_is_epic and not c_is_epic: continue
                        if c_is_omni and not f_is_omni: continue
                        if f_is_omni and not c_is_omni: continue
                        if c_is_mw and not f_is_mw: continue
                        if f_is_mw and not c_is_mw: continue
                        if c_is_comp and not f_is_comp: continue
                        if f_is_comp and not c_is_comp: continue
                        if c_is_tpb and not f_is_tpb: continue
                        if f_is_tpb and not c_is_tpb: continue

                        score, is_match = -1, False
                        c_core_flat = c_core.replace(" ", "")
                        f_core_flat = f_core.replace(" ", "")
                        
                        if c_core == f_core: 
                            is_match, score = True, 100
                        elif c_core_flat and f_core_flat and c_core_flat == f_core_flat: 
                            is_match, score = True, 90
                        else:
                            c_words, f_words = set(c_core.split()), set(f_core.split())
                            if c_words and f_words and (c_words.issubset(f_words) or f_words.issubset(c_words)):
                                min_len = min(len(c_words), len(f_words))
                                max_len = max(len(c_words), len(f_words))
                                extra_words = max_len - min_len
                                
                                is_any_coll = (c_is_epic or f_is_epic or c_is_mw or f_is_mw or c_is_omni or f_is_omni or c_is_comp or f_is_comp or c_is_tpb or f_is_tpb or "collection" in c_clean or "collection" in f_clean)
                                
                                if is_any_coll:
                                    is_match, score = True, 85 - (extra_words * 2)
                                else:
                                    # THE SHORT SERIES SHIELD!
                                    if min_len <= 2 and extra_words >= 1:
                                        pass 
                                    else:
                                        is_match, score = True, 80 - (extra_words * 5)

                            if not is_match and c_core_flat and f_core_flat:
                                if abs(len(c_core_flat) - len(f_core_flat)) < 10:
                                    ratio = difflib.SequenceMatcher(None, c_core_flat, f_core_flat).ratio()
                                    if ratio >= 0.93: 
                                        is_match, score = True, int(ratio * 100)

                        if is_match:
                            if c_year and comic['year']:
                                try:
                                    y_diff = abs(int(c_year) - int(comic['year']))
                                    if y_diff == 0: score += 20
                                    elif y_diff <= 1: score += 10
                                    elif y_diff > 2: 
                                        is_any_coll = (c_is_epic or f_is_epic or c_is_mw or f_is_mw or c_is_omni or f_is_omni or c_is_comp or f_is_comp or c_is_tpb or f_is_tpb or "collection" in c_clean or "collection" in f_clean)
                                        if not is_any_coll:
                                            # --- DOUBLE SHIELD 2: THE LETHAL YEAR PENALTY ---
                                            # Drops a 100% match to a 30% score (Instant Fail)
                                            score -= 70 
                                except ValueError: pass
                                
                            if score >= 40 and score > best_score:
                                best_score = score
                                found_path = comic['path']

                    search_query = f"MISSING:{c_series} {c_num} {c_year}".strip()
                    matches_to_draw.append({
                        "display_name": display_name,
                        "path": found_path if found_path else "",
                        "search_query": search_query
                    })

                cache_data[cbl_path] = {'mtime': cbl_mtime, 'matches': matches_to_draw}
                try:
                    with open(cache_file, 'w') as f: json.dump(cache_data, f)
                except Exception as _e:
                    log.warning("Suppressed exception: %s", _e)
            # =========================================================
            # PHASE 2: INSTANT RENDERING (From Memory)
            # =========================================================
            owned_files_to_load = []
            owned_count = 0
            missing_count = 0
            
            for match in matches_to_draw:
                safe_path = match["path"]
                display_name = match["display_name"]
                
                if safe_path and os.path.exists(safe_path):
                    owned_count += 1
                    safe_path = os.path.normpath(safe_path)
                    
                    if safe_path in getattr(self, 'reading_history', set()):
                        display_name = "✅ " + display_name

                    item = QListWidgetItem(display_name)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setData(Qt.ItemDataRole.UserRole, safe_path)
                    
                    pixmap = QPixmap(180, 270)
                    pixmap.fill(QColor("#21222c")) 
                    painter = QPainter(pixmap)
                    painter.setPen(QColor("#50fa7b")) 
                    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "⏳ Loading...")
                    painter.end()
                    
                    item.setIcon(QIcon(pixmap))
                    item.setForeground(QColor("#50fa7b")) 
                    
                    owned_files_to_load.append(safe_path)
                    self.grid_list.addItem(item)
                    
                    if safe_path not in self.grid_items_map:
                        self.grid_items_map[safe_path] = []
                    self.grid_items_map[safe_path].append(item)
                    
                else:
                    missing_count += 1
                    item = QListWidgetItem(display_name)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    
                    pixmap = QPixmap(180, 270)
                    pixmap.fill(QColor("#44475a")) 
                    painter = QPainter(pixmap)
                    painter.setPen(QColor("#ff5555")) 
                    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "❌ MISSING\n\nClick to\nSearch Web")
                    painter.end()

                    item.setIcon(QIcon(pixmap))
                    item.setForeground(QColor("#ff5555"))
                    item.setData(Qt.ItemDataRole.UserRole, match["search_query"])
                    self.grid_list.addItem(item)

            if hasattr(self, 'cbl_stats_label'):
                total_count = owned_count + missing_count
                self.cbl_stats_label.setText(f"📚 Total: {total_count}  |  ✅ Owned: {owned_count}  |  ❌ Missing: {missing_count}")
                self.cbl_stats_label.show()

            if owned_files_to_load:
                unique_files = list(set(owned_files_to_load))
                self.cover_thread = CoverLoaderThread(unique_files)
                self.cover_thread.cover_loaded.connect(self.update_grid_icon)
                self.cover_thread.start()
                
        except Exception as e:
            print(f"Failed to generate CBL Grid: {e}")
            
        self.grid_list.setUpdatesEnabled(True)

    def update_grid_icon(self, path, cover_bytes):
        norm = os.path.normpath(path)
        # Store raw bytes keyed by normpath so the slider can re-render later
        if not hasattr(self, '_cover_bytes_cache'):
            self._cover_bytes_cache = {}
        if cover_bytes:
            self._cover_bytes_cache[norm] = cover_bytes

        # grid_items_map keys may or may not be normpathed — try both
        item_map = getattr(self, 'grid_items_map', {})
        items = item_map.get(path) or item_map.get(norm)
        if items is None:
            return
        if not isinstance(items, list):
            items = [items]
        alive_items = []
        for item in items:
            try:
                _ = item.text()
                alive_items.append(item)
            except RuntimeError:
                pass
        if not alive_items:
            return

        w = APP_SETTINGS.get('grid_size', 180)
        h = int(w * 1.5)
        self._set_grid_item_icon(alive_items, cover_bytes, w, h)

    def on_tree_right_click(self, position):
        
        index = self.tree.indexAt(position)
        if not index.isValid():
            return
            
        source_index = self.proxy_model.mapToSource(index)
        path = self.model.filePath(source_index)
        
        menu = QMenu(self)
        
        menu.setStyleSheet("""
            QMenu { background-color: #282a36; color: #f8f8f2; border: 1px solid #44475a; } 
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #44475a; }
        """)
        
        open_action = menu.addAction("📂 Open in File Explorer")
        tagger_action = menu.addAction("🏷️ Send to Tagger")
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        
        if action == open_action:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            try:
                os.startfile(folder)
            except Exception as e:
                print(f"Could not open folder: {e}")
        elif action == tagger_action:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            self._ensure_tab_built(self._TAB_TAGGER)
            self.tagger_tab.receive_folder(folder)
            self.tabs.setCurrentIndex(self._TAB_TAGGER)
                
    # --- IDEA 3: EXPORT FOLDER AS .CBL ---
    def on_tree_right_click(self, position):
        
        index = self.tree.indexAt(position)
        if not index.isValid():
            return
            
        source_index = self.proxy_model.mapToSource(index)
        path = self.model.filePath(source_index)
        
        menu = QMenu(self)
        
        # THE FIX: Force the dark theme onto this specific pop-up menu!
        menu.setStyleSheet("""
            QMenu { background-color: #282a36; color: #f8f8f2; border: 1px solid #44475a; } 
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #44475a; }
        """)
        
        open_action = menu.addAction("📂 Open in File Explorer")
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        
        if action == open_action:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            try:
                os.startfile(folder)
            except Exception as e:
                print(f"Could not open folder: {e}")

    def export_folder_to_cbl(self):

        item = self.lib_list.currentItem()
        if not item: return
        folder_path = item.text()
        if not os.path.exists(folder_path): return

        name, ok = QInputDialog.getText(self, "Export to CBL", "Enter Reading List Name:", text=os.path.basename(folder_path))
        if not ok or not name: return

        # Grab all comics in the folder AND subfolders
        comics = []
        for root, _, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith(('.cbz', '.cbr')):
                    comics.append(os.path.join(root, f))
                    
        if not comics:
            QMessageBox.warning(self, "Empty Folder", "No comics found to export!")
            return

        # Sort them naturally so Issue 2 comes before Issue 10
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
        comics.sort(key=natural_sort_key)

        # Build the CBL XML Structure
        root_element = ET.Element("ReadingList", {"xmlns:xsd": "http://www.w3.org/2001/XMLSchema", "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"})
        ET.SubElement(root_element, "Name").text = name
        ET.SubElement(root_element, "NumIssues").text = str(len(comics))
        books_element = ET.SubElement(root_element, "Books")

        for path in comics:
            series, number, year = "", "", ""
            
            # ==========================================
            # 1. TRY COMICINFO.XML FIRST (Gold Standard)
            # ==========================================
            if path.lower().endswith('.cbz'):
                try:
                    with zipfile.ZipFile(path, 'r') as zf:
                        if 'ComicInfo.xml' in zf.namelist():
                            xml_data = zf.read('ComicInfo.xml')
                            c_root = ET.fromstring(xml_data)
                            
                            s_node = c_root.find('Series')
                            n_node = c_root.find('Number')
                            y_node = c_root.find('Year')
                            
                            if s_node is not None and s_node.text: series = str(s_node.text).strip()
                            if n_node is not None and n_node.text: number = str(n_node.text).strip()
                            if y_node is not None and y_node.text: year = str(y_node.text).strip()
                except Exception as _e:
                    log.warning("Suppressed exception: %s", _e)
            # ==========================================
            # 2. SMART FALLBACK (Fill in the blanks!)
            # ==========================================
            filename = os.path.basename(path)
            base_name = os.path.splitext(filename)[0]
            clean_name = re.sub(r'\(.*?\)|\[.*?\]', '', base_name).strip()
            
            if not year:
                y_match = re.search(r'[\[\(](\d{4})[\]\)]', base_name)
                if y_match: year = y_match.group(1)
                
            if not series or not number:
                f_issue = ""
                f_series = clean_name
                
                # Our bulletproof scanner
                m_hash = re.search(r'#\s*0*(\d+)', clean_name)
                m_vol_and_iss = re.search(r'(?i)\b(?:v|vol|volume)\.?\s*\d+(?:\s*[-–—:]\s*|\s+)0*(\d+)', clean_name)
                m_vol = re.search(r'(?i)\b(?:v|vol|volume|book|bk|tpb)\.?\s*0*(\d+)', clean_name)
                m_dash = re.search(r'\b0*(\d+)\s*[-–—:]', clean_name)
                m_end = re.search(r'\b0*(\d+)$', clean_name)
                m_trap = re.search(r'\s+0*(\d+)\b', clean_name)
                
                if m_hash:
                    f_issue = str(int(m_hash.group(1)))
                    cut = m_hash.start()
                    mv = re.search(r'(?i)\b(?:v|vol|volume)\.?\s*\d+', clean_name)
                    if mv and mv.start() < cut: cut = mv.start()
                    f_series = clean_name[:cut].strip()
                elif m_vol_and_iss:
                    f_issue = str(int(m_vol_and_iss.group(1)))
                    mv_start = re.search(r'(?i)\b(?:v|vol|volume)\.?\s*\d+', clean_name).start()
                    f_series = clean_name[:mv_start].strip()
                elif m_vol:
                    f_issue = str(int(m_vol.group(1)))
                    f_series = clean_name[:m_vol.start()].strip()
                elif m_dash:
                    f_issue = str(int(m_dash.group(1)))
                    f_series = clean_name[:m_dash.start()].strip()
                elif m_end:
                    f_issue = str(int(m_end.group(1)))
                    f_series = clean_name[:m_end.start()].strip()
                elif m_trap and m_trap.group(1) not in ['2099', '1602', '3000']:
                    f_issue = str(int(m_trap.group(1)))
                    f_series = clean_name[:m_trap.start()].strip()

                # Only overwrite if the XML was actually blank!
                if not series: series = f_series
                if not number: number = f_issue

            # Add it to the CBL
            book = ET.SubElement(books_element, "Book")
            if series: ET.SubElement(book, "Series").text = series
            if number: ET.SubElement(book, "Number").text = number
            if year: ET.SubElement(book, "Year").text = year

        # Save the file!
        cbl_path = os.path.join(folder_path, f"{name}.cbl")
        xml_str = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root_element, encoding='unicode')
        
        try:
            with open(cbl_path, 'w', encoding='utf-8') as f:
                f.write(xml_str)
            QMessageBox.information(self, "Success", f"Exported {len(comics)} comics to:\n{cbl_path}")
            
            # Refresh the library view so it shows up instantly
            if hasattr(self, 'library_model'):
                self.library_model.layoutChanged.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not write CBL file:\n{str(e)}")
    
    
    def load_comic_data(self, file_path):
        file_path = os.path.normpath(file_path)
        self.action_btn.setEnabled(True)
        self.update_local_nav_buttons() 
        try:
            file_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
            cache_path = os.path.join(CACHE_DIR, f"{file_hash}.jpg")
            img_data = None

            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    img_data = f.read()

            if file_path.lower().endswith('.cbz'):
                archive = zipfile.ZipFile(file_path, 'r')
            else:
                archive = rarfile.RarFile(file_path, 'r')

            with archive as af:
                file_list = af.namelist()
                if not img_data:
                    image_files = [f for f in file_list if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                    image_files = [f for f in image_files if not f.endswith('/') and not f.endswith('\\')]
                    image_files.sort()
                    if image_files:
                        img_data = af.read(image_files[0])
                        try:
                            with open(cache_path, 'wb') as f: f.write(img_data)
                        except Exception as _e:
                            log.warning("Suppressed exception: %s", _e)
                if img_data:
                    pixmap = QPixmap()
                    pixmap.loadFromData(img_data)
                    w = getattr(self, '_cover_size', 250)
                    h = int(w * 1.52)
                    scaled_pixmap = pixmap.scaled(
                        w, h,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.cover_label.setPixmap(scaled_pixmap)
                else:
                    self.cover_label.setText("No images found.")

                raw_filename = os.path.basename(file_path)
                filename_only, _ = os.path.splitext(raw_filename)
                xml_filename = next((f for f in file_list if f.lower() == 'comicinfo.xml'), None)
                
                if xml_filename:
                    xml_data = af.read(xml_filename)
                    xml_str = xml_data.decode('utf-8', errors='ignore')
                    xml_str = re.sub(r'\sxmlns="[^"]+"', '', xml_str, count=1)
                    self._current_xml_str = xml_str  # stash for dialog
                    self.more_info_btn.setEnabled(True)
                    root = ET.fromstring(xml_str)
                    
                    # 1. Extract our new tags!
                    series = root.findtext('Series', '')
                    story_arc = root.findtext('StoryArc', '')
                    title = root.findtext('Title', 'Unknown Title')
                    writer = root.findtext('Writer', 'Unknown Writer')
                    artist = root.findtext('Penciller', root.findtext('Artist', 'Unknown Artist'))
                    summary = root.findtext('Summary', 'No summary available.')
                    
                    # 2. Dynamically build the UI components
                    series_html = f'<div style="color: #50fa7b; font-weight: bold; font-size: 20px; margin-bottom: 2px;">{series}</div>' if series else ''
                    title_html = f'<h3 style="color: #8be9fd; margin-top: 5px; margin-bottom: 10px;">{title}</h3>' if title and title != "Unknown Title" else ''
                    arc_html = f'<div style="margin-bottom: 5px; color: #ffb86c;"><b>Story Arc:</b> {story_arc}</div>' if story_arc else ''
                    
                    # 3. Stitch it all together!
                    html_content = f"""
                        {series_html}
                        <div style="color: #ffffff; font-size: 11px; font-style: italic; margin-bottom: 10px;">{filename_only}</div>
                        {title_html}
                        {arc_html}
                        <div><b>Writer:</b> {writer}</div>
                        <div><b>Artist:</b> {artist}</div>
                        <hr><div>{summary}</div>
                    """
                    self.info_box.setHtml(html_content)
                else:
                    self._current_xml_str = None
                    self.more_info_btn.setEnabled(False)
                    self.info_box.setHtml(f"<div style='color: #ffffff; font-size: 11px; font-style: italic; margin-bottom: 10px;'>{filename_only}</div><h3 style='color:#f1fa8c;'>No Metadata found.</h3>")

        except Exception as e:
            self.info_box.setHtml(f"<p style='color: #ff5555;'>Error reading file: {e}</p>")
    
    def show_metadata_dialog(self):
        if not self.current_comic_path or not self._current_xml_str:
            return
        dlg = ComicMetadataDialog(self._current_xml_str, self.current_comic_path, self)
        dlg.exec()
        self.load_comic_data(self.current_comic_path)

    def _set_grid_item_icon(self, items, cover_bytes, w, h):
        """Render cover_bytes at w x h and apply to items. Uses a fallback tile if no bytes."""
        pixmap = QPixmap()
        if cover_bytes and pixmap.loadFromData(cover_bytes) and not pixmap.isNull():
            scaled = pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            icon = QIcon(scaled)
        else:
            fallback = QPixmap(w, h)
            fallback.fill(QColor('#44475a'))
            painter = QPainter(fallback)
            painter.setPen(QColor('#ffb86c'))
            painter.drawText(fallback.rect(), Qt.AlignmentFlag.AlignCenter, 'No Cover\nFound')
            painter.end()
            icon = QIcon(fallback)
        for item in items:
            try:
                item.setIcon(icon)
                item.setForeground(Qt.GlobalColor.white)
            except RuntimeError:
                pass

    def _on_grid_size_changed(self, value):
        h = int(value * 1.5)
        self.grid_list.setIconSize(QSize(value, h))
        self.grid_list.setGridSize(QSize(value + 40, h + 50))
        self.grid_size_label.setText(str(value))
        APP_SETTINGS['grid_size'] = value
        try:
            with open('settings.json', 'w') as f:
                json.dump(APP_SETTINGS, f)
        except Exception as _e:
            log.warning('Could not save grid_size setting: %s', _e)

        # Re-render every visible icon at the new size from stored bytes
        cache = getattr(self, '_cover_bytes_cache', {})
        for path, items in getattr(self, 'grid_items_map', {}).items():
            if not isinstance(items, list):
                items = [items]
            alive = []
            for it in items:
                try:
                    _ = it.text()
                    alive.append(it)
                except RuntimeError:
                    pass
            if alive:
                norm = os.path.normpath(path)
                raw = cache.get(norm) or cache.get(path) or b''
                self._set_grid_item_icon(alive, raw, value, h)

        # Re-render folder stack icons at the new size
        folder_cache = getattr(self, '_folder_bytes_cache', {})
        for folder_path, item in getattr(self, 'grid_folder_map', {}).items():
            covers = folder_cache.get(os.path.normpath(folder_path), [])
            self.update_folder_icon(folder_path, covers)

    def save_hidden_paths(self):
        try:
            with open(self.hidden_file, 'w') as f:
                json.dump(list(self.hidden_paths), f)
        except Exception as _e:
            log.warning("Suppressed exception: %s", _e)
    def _make_cbl_icon(self, cbl_path: str, img_bytes: bytes = None) -> QIcon:
        """Build and return a QIcon for a CBL tile.
        If img_bytes is provided it is used as the cover image.
        Otherwise checks the custom cache, then falls back to the 📋 default design."""
        gs = APP_SETTINGS.get('grid_size', 180)
        gh = int(gs * 1.5)

        # Check custom cache if no bytes supplied
        if not img_bytes:
            norm = os.path.normpath(cbl_path)
            file_hash = hashlib.md5(norm.encode('utf-8')).hexdigest()
            custom_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
            if os.path.exists(custom_path):
                try:
                    with open(custom_path, 'rb') as f:
                        img_bytes = f.read()
                except Exception as _e:
                    log.warning("Could not read CBL custom cover: %s", _e)

        # Draw with a real image if we have one
        if img_bytes:
            pixmap = QPixmap()
            if pixmap.loadFromData(img_bytes) and not pixmap.isNull():
                scaled = pixmap.scaled(gs, gh, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                canvas = QPixmap(gs, gh)
                canvas.fill(QColor('#21222c'))
                painter = QPainter(canvas)
                # Centre the scaled image
                ox = (gs - scaled.width())  // 2
                oy = (gh - scaled.height()) // 2
                painter.drawPixmap(ox, oy, scaled)
                # Amber border so it's still visually distinct as a CBL
                painter.setPen(QColor('#ffb86c'))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(0, 0, gs - 1, gh - 1)
                painter.end()
                return QIcon(canvas)

        # Default 📋 design
        pixmap = QPixmap(gs, gh)
        pixmap.fill(QColor('#21222c'))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor('#44475a'))
        painter.setBrush(QColor('#282a36'))
        painter.drawRoundedRect(int(gs * 0.06), int(gh * 0.06),
                                int(gs * 0.88), int(gh * 0.88), 6, 6)
        painter.setPen(QColor('#ffb86c'))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(8, gs // 20))
        painter.setFont(font)
        painter.drawText(0, 0, gs, int(gh * 0.35),
                         Qt.AlignmentFlag.AlignCenter, '\U0001f4cb')
        painter.end()
        return QIcon(pixmap)

    def _apply_cbl_cover(self, cbl_path: str, img_bytes: bytes):
        """Save img_bytes as the custom cover for a CBL and refresh its grid tile."""
        norm = os.path.normpath(cbl_path)
        file_hash = hashlib.md5(norm.encode('utf-8')).hexdigest()
        custom_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
        try:
            with open(custom_path, 'wb') as f:
                f.write(img_bytes)
        except Exception as _e:
            log.warning("Could not save CBL custom cover: %s", _e)
            return
        # Find the grid item and refresh its icon
        for i in range(self.grid_list.count()):
            it = self.grid_list.item(i)
            try:
                if str(it.data(Qt.ItemDataRole.UserRole)) == f"CBL:{cbl_path}":
                    it.setIcon(self._make_cbl_icon(cbl_path, img_bytes))
                    break
            except RuntimeError:
                pass

    def _go_to_file_in_tree(self, path: str):
        """Expand and select a file or folder in the left-panel tree."""
        path = os.path.normpath(path)

        # First make sure the library root that contains this path is loaded.
        # Walk up the directory tree and expand each level so the model
        # populates the path before we try to select it.
        ancestors = []
        p = path if os.path.isdir(path) else os.path.dirname(path)
        while True:
            ancestors.append(p)
            parent = os.path.dirname(p)
            if parent == p:  # reached drive root
                break
            p = parent
        ancestors.reverse()

        for ancestor in ancestors:
            src_idx = self.model.index(ancestor)
            if src_idx.isValid():
                proxy_idx = self.proxy_model.mapFromSource(src_idx)
                if proxy_idx.isValid():
                    self.tree.expand(proxy_idx)

        source_idx = self.model.index(path)
        if not source_idx.isValid():
            return
        proxy_idx = self.proxy_model.mapFromSource(source_idx)
        if not proxy_idx.isValid():
            return

        self.left_tabs.setCurrentIndex(0)
        self.tree.setCurrentIndex(proxy_idx)
        self.tree.scrollTo(proxy_idx, QAbstractItemView.ScrollHint.PositionAtCenter)

    def show_grid_context_menu(self, pos):
        
        item = self.grid_list.itemAt(pos)
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background-color: #282a36; color: #f8f8f2; border: 1px solid #44475a; } 
            QMenu::item:selected { background-color: #44475a; }
        """)
        
        # IF YOU CLICKED EMPTY BACKGROUND SPACE -> UNHIDE OPTION!
        if not item:
            unhide_action = menu.addAction("👁️ Unhide All Hidden Items")
            action = menu.exec(self.grid_list.mapToGlobal(pos))
            if action == unhide_action:
                self.hidden_paths.clear()
                self.save_hidden_paths()
                self.proxy_model.invalidateFilter() # Refresh Left Tree
                if getattr(self, 'current_grid_folder', None):
                    self.load_folder_grid(self.current_grid_folder) # Refresh Grid
            return

        # IF YOU CLICKED A COMIC/FOLDER -> HIDE & EDIT OPTIONS!
        user_str = str(item.data(Qt.ItemDataRole.UserRole) or "")

        # CBL gets its own menu
        if user_str.startswith("CBL:"):
            cbl_path = user_str[4:]
            open_cbl_action    = menu.addAction("📋 Open Reading List")
            goto_cbl_action    = menu.addAction("📍 Go to File Location")
            menu.addSeparator()
            cbl_img_action     = menu.addAction("🖼️ Set Custom Image Cover")
            cbl_comic_action   = menu.addAction("📕 Pick Comic as Cover")
            cbl_reset_action   = menu.addAction("🔄 Reset to Default Cover")
            action = menu.exec(self.grid_list.mapToGlobal(pos))
            if action == open_cbl_action and os.path.exists(cbl_path):
                self.tabs.setCurrentIndex(1)
                self.load_cbl_grid(cbl_path)
            elif action == goto_cbl_action:
                self._go_to_file_in_tree(cbl_path)
            elif action == cbl_img_action:
                img_path, _ = QFileDialog.getOpenFileName(
                    self, "Select Cover Image", "", "Images (*.png *.jpg *.jpeg *.webp)")
                if img_path:
                    with open(img_path, 'rb') as f:
                        self._apply_cbl_cover(cbl_path, f.read())
            elif action == cbl_comic_action:
                comic_path, _ = QFileDialog.getOpenFileName(
                    self, "Select Comic to use as Cover", "", "Comic Archives (*.cbz *.cbr)")
                if comic_path:
                    valid_exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
                    img_bytes = None
                    try:
                        if comic_path.lower().endswith('.cbz'):
                            with zipfile.ZipFile(comic_path, 'r') as zf:
                                imgs = sorted(f for f in zf.namelist()
                                              if f.lower().endswith(valid_exts)
                                              and "__MACOSX" not in f)
                                if imgs: img_bytes = zf.read(imgs[0])
                        else:
                            with rarfile.RarFile(comic_path, 'r') as rf:
                                imgs = sorted(f for f in rf.namelist()
                                              if f.lower().endswith(valid_exts))
                                if imgs: img_bytes = rf.read(imgs[0])
                    except Exception as _e:
                        log.warning("CBL comic cover extract failed: %s", _e)
                    if img_bytes:
                        self._apply_cbl_cover(cbl_path, img_bytes)
                    else:
                        QMessageBox.warning(self, "Error", "Could not extract an image from that comic.")
            elif action == cbl_reset_action:
                norm = os.path.normpath(cbl_path)
                file_hash = hashlib.md5(norm.encode('utf-8')).hexdigest()
                custom_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
                if os.path.exists(custom_path):
                    try: os.remove(custom_path)
                    except Exception as _e: log.warning("CBL reset cover failed: %s", _e)
                # Redraw with default design
                for i in range(self.grid_list.count()):
                    it = self.grid_list.item(i)
                    try:
                        if str(it.data(Qt.ItemDataRole.UserRole)) == f"CBL:{cbl_path}":
                            it.setIcon(self._make_cbl_icon(cbl_path))
                            break
                    except RuntimeError:
                        pass
            return

        link_action = menu.addAction("🔗 Smart-Link Comic(s)")
        tagger_action = menu.addAction("🏷️ Send to Tagger")
        goto_action = menu.addAction("📍 Go to File Location")
        menu.addSeparator()
        cover_internal_action = menu.addAction("📑 Change Cover (Select Internal)")
        cover_comic_action = menu.addAction("📕 Pick Comic as Cover")
        cover_img_action = menu.addAction("🖼️ Pick Custom Image Cover")
        menu.addSeparator()
        reset_action = menu.addAction("🔄 Reset to Default Cover")
        menu.addSeparator()
        hide_action = menu.addAction("🙈 Hide Item (Remove from Grid)")
        
        action = menu.exec(self.grid_list.mapToGlobal(pos))
        
        if action == link_action:
            self.manual_link_comics(item)
        elif action == tagger_action:
            if not user_str.startswith("MISSING:"):
                target_path = user_str.split("FOLDER:")[1] if user_str.startswith("FOLDER:") else user_str
                self._ensure_tab_built(self._TAB_TAGGER)
                self.tagger_tab.receive_folder(target_path)
                self.tabs.setCurrentIndex(self._TAB_TAGGER)
        elif action == goto_action:
            if not user_str.startswith("MISSING:"):
                if user_str.startswith("FOLDER:"):
                    target_path = user_str[7:]
                elif user_str.startswith("CBL:"):
                    target_path = user_str[4:]
                else:
                    target_path = user_str
                self._go_to_file_in_tree(target_path)
        elif action == cover_img_action:
            self.pick_custom_cover(item)
        elif action == cover_comic_action:
            self.pick_comic_as_cover(item)
        elif action == cover_internal_action:
            self.select_internal_cover(item)
        elif action == reset_action:
            self.reset_default_cover(item)
        elif action == hide_action:
            if not user_str.startswith("MISSING:"): 
                target_path = user_str.split("FOLDER:")[1] if user_str.startswith("FOLDER:") else user_str
                norm_path = os.path.normpath(target_path)
                
                # 1. Save it to the ban list
                self.hidden_paths.add(norm_path)
                self.save_hidden_paths()
                
                # 2. Tell the left tree to hide it instantly
                self.proxy_model.invalidateFilter() 
                
                # 3. Pop it out of the grid UI instantly
                self.grid_list.takeItem(self.grid_list.row(item))
        elif action == reset_action:
            self.reset_default_cover(item)

    def pick_custom_cover(self, item):
        
        user_str = str(item.data(Qt.ItemDataRole.UserRole))
        if user_str.startswith("MISSING:"): return 
        
        is_folder = False
        target_path = user_str
        if user_str.startswith("FOLDER:"):
            is_folder = True
            target_path = user_str.split("FOLDER:")[1]
            
        img_path, _ = QFileDialog.getOpenFileName(self, "Select Custom Cover", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not img_path: return
        
        # Save securely to cache
        target_norm = os.path.normpath(target_path)
        file_hash = hashlib.md5(target_norm.encode('utf-8')).hexdigest()
        custom_cache_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
        
        shutil.copy(img_path, custom_cache_path)
        
        # Reload visually right now
        with open(custom_cache_path, 'rb') as f:
            img_bytes = f.read()
            
        if is_folder:
            self.update_folder_icon(target_path, [img_bytes])
        else:
            self.update_grid_icon(target_path, img_bytes)

    def pick_comic_as_cover(self, item):
        
        user_str = str(item.data(Qt.ItemDataRole.UserRole))
        if user_str.startswith("MISSING:"): return 
        
        is_folder = False
        target_path = user_str
        if user_str.startswith("FOLDER:"):
            is_folder = True
            target_path = user_str.split("FOLDER:")[1]
            
        # 1. Ask for a COMIC file instead of an image
        comic_path, _ = QFileDialog.getOpenFileName(self, "Select Comic to use as Cover", "", "Comic Archives (*.cbz *.cbr)")
        if not comic_path: return
        
        # 2. Quietly extract the cover from the selected comic
        img_bytes = None
        valid_exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif') 
        
        def try_zip(p):
            try:
                with zipfile.ZipFile(p, 'r') as zf:
                    names = zf.namelist()
                    images = [f for f in names if f.lower().endswith(valid_exts) and "__MACOSX" not in f and not os.path.basename(f).startswith('.')]
                    images.sort()
                    if images: return zf.read(images[0])
            except: return None
            return None
            
        def try_rar(p):
            try:
                with rarfile.RarFile(p, 'r') as rf:
                    names = rf.namelist()
                    images = [f for f in names if f.lower().endswith(valid_exts) and "__MACOSX" not in f and not os.path.basename(f).startswith('.')]
                    images.sort()
                    if images: return rf.read(images[0])
            except: return None
            return None
            
        if comic_path.lower().endswith('.cbz'):
            img_bytes = try_zip(comic_path)
            if not img_bytes: img_bytes = try_rar(comic_path)
        else:
            img_bytes = try_rar(comic_path)
            if not img_bytes: img_bytes = try_zip(comic_path)
            
        if not img_bytes:
            QMessageBox.warning(self, "Error", "Could not extract an image from that comic.")
            return
        
        # 3. Save securely to cache so it never touches the original file
        target_norm = os.path.normpath(target_path)
        file_hash = hashlib.md5(target_norm.encode('utf-8')).hexdigest()
        custom_cache_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
        
        with open(custom_cache_path, 'wb') as f:
            f.write(img_bytes)
            
        # 4. Reload visually right now
        if is_folder:
            self.update_folder_icon(target_path, [img_bytes])
        else:
            self.update_grid_icon(target_path, img_bytes)

    def reset_default_cover(self, item):
        
        user_str = str(item.data(Qt.ItemDataRole.UserRole))
        if user_str.startswith("MISSING:"): return 
        
        is_folder = False
        target_path = user_str
        if user_str.startswith("FOLDER:"):
            is_folder = True
            target_path = user_str.split("FOLDER:")[1]
            
        # Delete the custom override from the cache!
        target_norm = os.path.normpath(target_path)
        file_hash = hashlib.md5(target_norm.encode('utf-8')).hexdigest()
        custom_cache_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
        
        if os.path.exists(custom_cache_path):
            try: os.remove(custom_cache_path)
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
        # Force a refresh!
        if is_folder:
            self.folder_cover_thread = FolderCoverLoaderThread([target_path])
            self.folder_cover_thread.folder_cover_loaded.connect(self.update_folder_icon)
            self.folder_cover_thread.start()
        else:
            self.cover_thread = CoverLoaderThread([target_path])
            self.cover_thread.cover_loaded.connect(self.update_grid_icon)
            self.cover_thread.start()

    def select_internal_cover(self, item):
        
        user_str = str(item.data(Qt.ItemDataRole.UserRole))
        if user_str.startswith("MISSING:"): return 
        
        is_folder = False
        target_path = user_str
        if user_str.startswith("FOLDER:"):
            is_folder = True
            target_path = user_str.split("FOLDER:")[1]
            
        valid_exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
        images_bytes = []
        
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
            
        # Helper to extract images safely, even if extensions are lying
        def try_zip(p, multiple=False):
            try:
                with zipfile.ZipFile(p, 'r') as zf:
                    names = sorted([n for n in zf.namelist() if n.lower().endswith(valid_exts) and "__MACOSX" not in n and not os.path.basename(n).startswith('.')])
                    if not names: return [] if multiple else None
                    if multiple: return [zf.read(n) for n in names[:15]]
                    return zf.read(names[0])
            except: return [] if multiple else None
            
        def try_rar(p, multiple=False):
            try:
                with rarfile.RarFile(p, 'r') as rf:
                    names = sorted([n for n in rf.namelist() if n.lower().endswith(valid_exts) and "__MACOSX" not in n and not os.path.basename(n).startswith('.')])
                    if not names: return [] if multiple else None
                    if multiple: return [rf.read(n) for n in names[:15]]
                    return rf.read(names[0])
            except: return [] if multiple else None

        # --- EXTRACT THE IMAGES! ---
        if is_folder:
            # It's a folder: Grab the FIRST comic from EACH folder!
            try:
                files = os.listdir(target_path)
                top_paths = []
                
                # 1. Grab the FIRST comic sitting directly in the root folder (if any)
                comics = [f for f in files if f.lower().endswith(('.cbz', '.cbr'))]
                comics.sort(key=natural_sort_key)
                if comics:
                    top_paths.append(os.path.join(target_path, comics[0]))
                
                # 2. Grab the FIRST comic from each subfolder!
                subdirs = [f for f in files if os.path.isdir(os.path.join(target_path, f))]
                subdirs.sort(key=natural_sort_key)
                for subdir in subdirs:
                    if len(top_paths) >= 15: break
                    sub_path = os.path.join(target_path, subdir)
                    try:
                        sub_files = [f for f in os.listdir(sub_path) if f.lower().endswith(('.cbz', '.cbr'))]
                        if sub_files:
                            sub_files.sort(key=natural_sort_key)
                            top_paths.append(os.path.join(sub_path, sub_files[0]))
                    except Exception as _e:
                        log.warning("Suppressed exception: %s", _e)
                # 3. FALLBACK: If we still don't have 15 options, fill the rest with the remaining comics!
                if len(top_paths) < 15:
                    for c in comics[1:]:
                        if len(top_paths) >= 15: break
                        p = os.path.join(target_path, c)
                        if p not in top_paths: top_paths.append(p)
                        
                if len(top_paths) < 15:
                    for subdir in subdirs:
                        if len(top_paths) >= 15: break
                        sub_path = os.path.join(target_path, subdir)
                        try:
                            sub_files = [f for f in os.listdir(sub_path) if f.lower().endswith(('.cbz', '.cbr'))]
                            sub_files.sort(key=natural_sort_key)
                            for sf in sub_files[1:]:
                                if len(top_paths) >= 15: break
                                p = os.path.join(sub_path, sf)
                                if p not in top_paths: top_paths.append(p)
                        except Exception as _e:
                            log.warning("Suppressed exception: %s", _e)
                # 4. Extract the covers from our carefully curated list
                for p in top_paths[:15]:
                    img = None
                    if p.lower().endswith('.cbz'):
                        img = try_zip(p)
                        if not img: img = try_rar(p)
                    else:
                        img = try_rar(p)
                        if not img: img = try_zip(p)
                    if img: images_bytes.append(img)
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
        else:
            # It's a file: Grab the first 15 pages of the comic
            try:
                imgs = []
                if target_path.lower().endswith('.cbz'):
                    imgs = try_zip(target_path, multiple=True)
                    if not imgs: imgs = try_rar(target_path, multiple=True)
                else:
                    imgs = try_rar(target_path, multiple=True)
                    if not imgs: imgs = try_zip(target_path, multiple=True)
                if imgs: images_bytes.extend(imgs)
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
        if not images_bytes:
            QMessageBox.warning(self, "No Images", "Could not extract images to choose from.")
            return
            
        # --- SHOW THE SELECTION UI ---
        dialog = CoverSelectionDialog(images_bytes, self)
        if dialog.exec() == 1 and dialog.selected_bytes:
            # Save it!
            target_norm = os.path.normpath(target_path)
            file_hash = hashlib.md5(target_norm.encode('utf-8')).hexdigest()
            custom_cache_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
            
            with open(custom_cache_path, 'wb') as f:
                f.write(dialog.selected_bytes)
                
            # Reload visually right now
            if is_folder:
                self.update_folder_icon(target_path, [dialog.selected_bytes])
            else:
                self.update_grid_icon(target_path, dialog.selected_bytes)
        
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

        # --- EXTRACT THE IMAGES! ---
        if is_folder:
            # It's a folder: Grab the cover of the first 15 comics
            try:
                files = os.listdir(target_path)
                comics = [f for f in files if f.lower().endswith(('.cbz', '.cbr'))]
                comics.sort(key=natural_sort_key)
                
                for c in comics[:15]:
                    p = os.path.join(target_path, c)
                    img = None
                    try:
                        if p.lower().endswith('.cbz'):
                            with zipfile.ZipFile(p, 'r') as zf:
                                names = sorted([n for n in zf.namelist() if n.lower().endswith(valid_exts) and "__MACOSX" not in n and not os.path.basename(n).startswith('.')])
                                if names: img = zf.read(names[0])
                        else:
                            with rarfile.RarFile(p, 'r') as rf:
                                names = sorted([n for n in rf.namelist() if n.lower().endswith(valid_exts) and "__MACOSX" not in n and not os.path.basename(n).startswith('.')])
                                if names: img = rf.read(names[0])
                    except Exception as _e:
                        log.warning("Suppressed exception: %s", _e)
                    if img: images_bytes.append(img)
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
        else:
            # It's a file: Grab the first 15 pages of the comic
            try:
                if target_path.lower().endswith('.cbz'):
                    with zipfile.ZipFile(target_path, 'r') as zf:
                        names = sorted([n for n in zf.namelist() if n.lower().endswith(valid_exts) and "__MACOSX" not in n and not os.path.basename(n).startswith('.')])
                        for n in names[:15]: images_bytes.append(zf.read(n))
                else:
                    with rarfile.RarFile(target_path, 'r') as rf:
                        names = sorted([n for n in rf.namelist() if n.lower().endswith(valid_exts) and "__MACOSX" not in n and not os.path.basename(n).startswith('.')])
                        for n in names[:15]: images_bytes.append(rf.read(n))
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
        if not images_bytes:
            QMessageBox.warning(self, "No Images", "Could not extract images to choose from.")
            return
            
        # --- SHOW THE SELECTION UI ---
        dialog = CoverSelectionDialog(images_bytes, self)
        if dialog.exec() == 1 and dialog.selected_bytes:
            # Save it!
            target_norm = os.path.normpath(target_path)
            file_hash = hashlib.md5(target_norm.encode('utf-8')).hexdigest()
            custom_cache_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
            
            with open(custom_cache_path, 'wb') as f:
                f.write(dialog.selected_bytes)
                
            # Reload visually right now
            if is_folder:
                self.update_folder_icon(target_path, [dialog.selected_bytes])
            else:
                self.update_grid_icon(target_path, dialog.selected_bytes)
    
    def manual_link_comics(self, start_item):

        # 1. Ask user for files (Allows selecting MULTIPLE files in any order!)
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select Comic(s) to Link", 
            "", 
            "Comic Archives (*.cbz *.cbr)"
        )
        if not file_paths: return

        # 2. Grab the Base Series name of the item we clicked to prevent cross-contamination
        clicked_text = start_item.text().split('\n')[0]
        base_match = re.search(r'^(.*?)\s*#', clicked_text)
        base_series = base_match.group(1).strip().lower() if base_match else clicked_text.split()[0].lower()

        # 3. SMART PARSER: Extract the issue number from every selected file!
        files_by_issue = {}
        fallback_files = []
        
        for path in file_paths:
            base_name = os.path.splitext(os.path.basename(path))[0]
            clean_name = re.sub(r'\(.*?\)|\[.*?\]', '', base_name).strip()
            
            m_hash = re.search(r'#\s*(\d+)', clean_name)
            m_vol_and_iss = re.search(r'(?i)\b(?:v|vol|volume)\.?\s*\d+(?:\s*[-–—:]\s*|\s+)(\d+)(?:\s+[-–—:]|\s*$)', clean_name)
            m_vol_only = re.search(r'(?i)\b(?:v|vol|volume|book|bk|tpb)\.?\s*(\d+)(?:\s+[-–—:]|\s*$)', clean_name)
            m_iss_only = re.search(r'\s+(\d+)(?:\s+[-–—:]|\s*$)', clean_name)
            
            f_issue = ""
            if m_hash: f_issue = str(int(m_hash.group(1)))
            elif m_vol_and_iss: f_issue = str(int(m_vol_and_iss.group(1)))
            elif m_vol_only: f_issue = str(int(m_vol_only.group(1)))
            elif m_iss_only: f_issue = str(int(m_iss_only.group(1)))
            
            if f_issue:
                files_by_issue[f_issue] = path
            else:
                fallback_files.append(path) # If we can't find a number, save it for later

        # 4. Open the Lightning Cache to save the overrides permanently
        cache_file = "cbl_match_cache.json"
        cache_data = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f: cache_data = json.load(f)
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
        matches = []
        if getattr(self, 'current_cbl_path', None) and self.current_cbl_path in cache_data:
            matches = cache_data[self.current_cbl_path].get('matches', [])

        files_to_load = []
        start_row = self.grid_list.row(start_item)
        
        # 5. THE AUTO-SLOTTER: Scan downward from where they clicked
        for row in range(start_row, self.grid_list.count()):
            # If we've successfully mapped all selected files, stop scanning!
            if not files_by_issue and not fallback_files:
                break
                
            item = self.grid_list.item(row)
            item_text = item.text().split('\n')[0]
            
            # Guard: Only fill slots that belong to the same series we clicked on!
            if base_series and base_series not in item_text.lower():
                continue 
                
            # Extract the issue number the grid slot is asking for
            slot_num_match = re.search(r'#(\d+)', item_text)
            if not slot_num_match:
                u_data = str(item.data(Qt.ItemDataRole.UserRole))
                if "MISSING:" in u_data:
                    slot_num_match = re.search(r'\s+(\d+)\s+', u_data.split("MISSING:")[1])
                    
            if slot_num_match:
                slot_issue = str(int(slot_num_match.group(1)))
                matched_path = None
                
                # MATHEMATICAL MATCH! Does this slot's issue number exist in our selected files?
                if slot_issue in files_by_issue:
                    matched_path = files_by_issue.pop(slot_issue) 
                elif fallback_files:
                    matched_path = fallback_files.pop(0)
                    
                if matched_path:
                    safe_path = os.path.normpath(matched_path)
                    
                    # Inject path into UI Item
                    item.setData(Qt.ItemDataRole.UserRole, safe_path)
                    
                    # Clean up the display name
                    if matches and row < len(matches):
                        display_name = matches[row].get("display_name", "Linked Comic")
                        matches[row]["path"] = safe_path
                    else:
                        display_name = os.path.basename(safe_path)
                        
                    item.setText(display_name)
                    
                    # Create a green "Loading" icon
                    pixmap = QPixmap(180, 270)
                    pixmap.fill(QColor("#21222c")) 
                    painter = QPainter(pixmap)
                    painter.setPen(QColor("#50fa7b")) 
                    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "⏳ Loading...")
                    painter.end()
                    item.setIcon(QIcon(pixmap))
                    item.setForeground(Qt.GlobalColor.white)
                    
                    if safe_path not in self.grid_items_map:
                        self.grid_items_map[safe_path] = []
                    self.grid_items_map[safe_path].append(item)
                    
                    files_to_load.append(safe_path)

        # 6. Save the cache to the hard drive
        if self.current_cbl_path and matches:
            cache_data[self.current_cbl_path]['matches'] = matches
            try:
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f)
            except Exception as _e:
                log.warning("Suppressed exception: %s", _e)
        # 7. Spin up the image extractor thread for the newly linked files!
        if files_to_load:
            unique_files = list(set(files_to_load))
            if getattr(self, 'cover_thread', None) and self.cover_thread.isRunning():
                self.cover_thread.stop()
                self.cover_thread.wait()
                
            self.cover_thread = CoverLoaderThread(unique_files)
            self.cover_thread.cover_loaded.connect(self.update_grid_icon)
            self.cover_thread.start()
    def on_tree_right_click(self, position):
        
        index = self.tree.indexAt(position)
        if not index.isValid():
            return
            
        source_index = self.proxy_model.mapToSource(index)
        path = self.model.filePath(source_index)
        
        menu = QMenu(self)
        
        menu.setStyleSheet("""
            QMenu { background-color: #282a36; color: #f8f8f2; border: 1px solid #44475a; } 
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #44475a; }
        """)
        
        open_action = menu.addAction("📂 Open in File Explorer")
        tagger_action = menu.addAction("🏷️ Send to Batch Tagger")
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        
        if action == open_action:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            try:
                os.startfile(folder)
            except Exception as e:
                print(f"Could not open folder: {e}")
        elif action == tagger_action:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            self._ensure_tab_built(self._TAB_TAGGER)
            self.tagger_tab.receive_folder(folder)
            self.tabs.setCurrentIndex(self._TAB_TAGGER)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #282a36; }
            QWidget { color: #f8f8f2; }
            
            /* --- GLOBAL MENU FIX: Fixes right-click in textboxes, chat, and browser! --- */
            QMenu { 
                background-color: #282a36; 
                color: #f8f8f2; 
                border: 1px solid #44475a; 
            }
            QMenu::item { 
                padding: 5px 25px; 
                background-color: transparent; 
            }
            QMenu::item:selected { 
                background-color: #44475a; 
            }
            QMenu::separator { 
                height: 1px; 
                background: #44475a; 
                margin: 5px 0px; 
            }
            /* ------------------------------------------------------------------------- */
            
            QTreeView, QListWidget, QTextBrowser { 
                background-color: #21222c; 
                border: 1px solid #44475a; 
            }
            QHeaderView::section {
                background-color: #282a36;
                color: #f8f8f2;
                padding: 5px;
                border: 1px solid #44475a;
            }
            
            QPushButton { background-color: #44475a; padding: 5px; border-radius: 3px; }
            QPushButton:hover { background-color: #6272a4; }
            QPushButton#read_btn { background-color: #50fa7b; color: #282a36; font-weight: bold; }
            
            QLineEdit, QComboBox { 
                background-color: #21222c; 
                border: 1px solid #44475a; 
                padding: 5px; 
            }
            QComboBox QAbstractItemView {
                background-color: #282a36;
                color: #f8f8f2;
                selection-background-color: #44475a;
            }
            
            QProgressBar {
                background-color: #282a36; 
                border: 1px solid #44475a;
                border-radius: 4px;
                text-align: center;
                color: #f8f8f2;
            }
            QProgressBar::chunk { background-color: #50fa7b; border-radius: 3px; }
            
            QTabWidget::pane { border: 1px solid #44475a; background: #282a36; }
            QTabBar::tab { background: #21222c; padding: 8px 15px; border: 1px solid #44475a; }
            QTabBar::tab:selected { background: #44475a; font-weight: bold; }
            
            QTabWidget#left_tabs > QTabBar::tab { padding: 8px 10px; width: 150px; }
            
            QSlider::groove:horizontal {
                border: 1px solid #44475a;
                height: 8px;
                background: #282a36;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #50fa7b;
                border: 1px solid #44475a;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            
            QScrollBar:vertical {
                border: none;
                background: #282a36;
                width: 14px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #6272a4;
                border-radius: 7px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #50fa7b; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            
            QScrollBar:horizontal {
                border: none;
                background: #282a36;
                height: 14px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #6272a4;
                border-radius: 7px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover { background: #50fa7b; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            
            QSplitter::handle {
                background-color: #44475a;
                margin: 2px;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #8be9fd;
            }
        """)
        self.read_btn.setObjectName("read_btn")


