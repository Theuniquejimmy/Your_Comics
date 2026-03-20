"""Background worker threads and proxy models for ComicVault."""
import asyncio
import hashlib
import html as _html_mod
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
import zipfile
import xml.etree.ElementTree as ET
import datetime as _dt

import requests
import patoolib
import markdown
from ebooklib import epub
from google import genai
import edge_tts

from config import COMIC_VINE_KEY, GEMINI_KEY, CACHE_DIR, log
from utils import (
    parse_comic_filename_full,
    generate_comicinfo_xml,
    inject_metadata_into_cbz,
    _the_variants,
    _norm_vol_name,
    _score_volume,
    _gc_first_article,
    force_remove_readonly,
    natural_sort_key,
)
from PyQt6.QtCore import Qt, QByteArray, QBuffer, QIODevice, QSortFilterProxyModel, QThread, pyqtSignal
from PyQt6.QtGui import QFileSystemModel, QImage

try:
    import rarfile
    rarfile.UNRAR_TOOL = r"C:\Program Files\WinRAR\UnRAR.exe"
    HAS_RAR = True
except ImportError:
    HAS_RAR = False


class MiniImageFetcher(QThread):
    image_ready = pyqtSignal(bytes)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            data = requests.get(self.url, timeout=5).content
            self.image_ready.emit(data)
        except Exception:
            self.image_ready.emit(b"")


class MiniVineSearcher(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        safe_query = urllib.parse.quote(self.query)
        url = f"https://comicvine.gamespot.com/api/search/?api_key={COMIC_VINE_KEY}&format=json&resources=issue&query={safe_query}"

        try:
            headers = {"User-Agent": "YourComicsApp/1.0"}
            resp = requests.get(url, headers=headers, timeout=10).json()
            if resp.get('error') == 'OK':
                self.results_ready.emit(resp.get('results', []))
            else:
                self.results_ready.emit([])
        except Exception:
            self.results_ready.emit([])


class MiniAITaggerThread(QThread):
    ai_ready = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, search_query):
        super().__init__()
        self.search_query = search_query

    def run(self):
        if not GEMINI_KEY:
            self.error_signal.emit("Missing Gemini API Key!")
            return

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_KEY)

            if self.search_query.startswith("http"):
                res = requests.get(self.search_query, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                scraped_text = re.sub(r'<[^>]+>', ' ', res.text)

                prompt = (
                    "You are a comic book metadata expert. I have scraped the text from a comic wiki/database page.\n"
                    "Extract the accurate metadata for the comic from this text.\n"
                    "Pay special attention to grabbing the FULL plot summary!\n\n"
                    f"SCRAPED TEXT:\n{scraped_text[:15000]}\n\n"
                    "You MUST return ONLY a raw JSON dictionary. Do not include markdown formatting.\n"
                    "The JSON must use these exact keys:\n"
                    "{\n"
                    '  "volume": {"name": "The Series Name"},\n'
                    '  "volume_number": "Volume number or year",\n'
                    '  "issue_number": "The issue number",\n'
                    '  "name": "Title of the specific arc/issue",\n'
                    '  "cover_date": "YYYY-MM-DD",\n'
                    '  "deck": "The exact plot summary or synopsis found in the text.",\n'
                    '  "story_arc": "The name of the story arc",\n'
                    '  "alternate_series": "If this is part of a crossover event, the event name",\n'
                    '  "alternate_number": "Reading order/issue number within the crossover event",\n'
                    '  "alternate_count": "Total number of issues in the crossover event",\n'
                    '  "person_credits": [\n'
                    '    {"name": "Writer Name", "role": "writer"},\n'
                    '    {"name": "Artist Name", "role": "artist"}\n'
                    '  ],\n'
                    '  "character_credits": [{"name": "Character Name"}],\n'
                    '  "team_credits": [{"name": "Team Name"}],\n'
                    '  "location_credits": [{"name": "Location Name"}]\n'
                    "}\n"
                )
                config = None

            else:
                prompt = (
                    f'You are a comic book metadata expert. Generate accurate metadata for a comic book titled "{self.search_query}".\n'
                    "USE GOOGLE SEARCH to find the exact plot, writers, artists, characters, and locations for this specific issue.\n"
                    "You MUST return ONLY a raw JSON dictionary. Do not include markdown formatting.\n"
                    "The JSON must use these exact keys:\n"
                    "{\n"
                    '  "volume": {"name": "The Series Name"},\n'
                    '  "volume_number": "The volume number or starting year",\n'
                    '  "issue_number": "The issue number",\n'
                    '  "name": "The title of the arc/issue",\n'
                    '  "cover_date": "YYYY-MM-DD",\n'
                    '  "deck": "A detailed 2-3 paragraph plot summary based on your Google Search.",\n'
                    '  "story_arc": "The name of the story arc",\n'
                    '  "alternate_series": "If this is part of a crossover event, the event name",\n'
                    '  "alternate_number": "Reading order/issue number within the crossover event",\n'
                    '  "alternate_count": "Total number of issues in the crossover event",\n'
                    '  "person_credits": [\n'
                    '    {"name": "Writer Name", "role": "writer"},\n'
                    '    {"name": "Artist Name", "role": "artist"}\n'
                    '  ],\n'
                    '  "character_credits": [{"name": "Character Name"}],\n'
                    '  "team_credits": [{"name": "Team Name"}],\n'
                    '  "location_credits": [{"name": "Location Name"}]\n'
                    "}\n"
                )
                config = types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=config
            )

            text = response.text.strip()
            bt = chr(96) * 3

            if text.startswith(bt + "json"):
                text = text[7:].strip()
            elif text.startswith(bt):
                text = text[3:].strip()

            if text.endswith(bt):
                text = text[:-3].strip()

            ai_data = json.loads(text)
            self.ai_ready.emit(ai_data)

        except Exception as e:
            self.error_signal.emit(str(e))


class ComicVineIssueThread(QThread):
    issue_ready = pyqtSignal(dict)

    def __init__(self, vol_id=None, issue_num=None, direct_api_url=None):
        super().__init__()
        self.vol_id = vol_id
        self.issue_num = issue_num
        self.direct_api_url = direct_api_url

    def run(self):
        headers = {"User-Agent": "YourComicsApp/1.0"}

        try:
            time.sleep(1.5)

            if self.direct_api_url:
                url = f"{self.direct_api_url}?api_key={COMIC_VINE_KEY}&format=json"

            else:
                issue_filter = f"volume:{self.vol_id}"
                if self.issue_num:
                    issue_filter += f",issue_number:{self.issue_num}"
                url = f"https://comicvine.gamespot.com/api/issues/?api_key={COMIC_VINE_KEY}&format=json&filter={urllib.parse.quote(issue_filter)}&field_list=id,name,issue_number,cover_date,volume,api_detail_url,page_count,image,language"

            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()

            if data.get('error') == 'OK':
                if self.direct_api_url:
                    self.issue_ready.emit(data.get('results', {}))
                else:
                    results = data.get('results', [])
                    self.issue_ready.emit(results[0] if results else {})
            else:
                self.issue_ready.emit({})

        except Exception as e:
            log.warning("Error fetching full issue data: %s", e)
            self.issue_ready.emit({})


class ComicConverterThread(QThread):
    finished_conversion = pyqtSignal(bool, str, str)
    progress_update = pyqtSignal(int, int)
    status_update = pyqtSignal(str)

    def __init__(self, file_path, xml_string):
        super().__init__()
        self.file_path = file_path
        self.xml_string = xml_string

    def run(self):
        try:
            dir_name = os.path.dirname(self.file_path)
            base_name, ext = os.path.splitext(os.path.basename(self.file_path))
            new_cbz_path = os.path.join(dir_name, base_name + ".cbz")

            if ext.lower() == '.cbz':
                if self.xml_string:
                    self.status_update.emit("Updating metadata (Fast Stream)...")
                    try:
                        inject_metadata_into_cbz(self.file_path, self.xml_string)
                        self.finished_conversion.emit(True, "Metadata injected instantly!", self.file_path)
                    except Exception as e:
                        self.finished_conversion.emit(False, f"Error: {e}", "")
                    return

            with tempfile.TemporaryDirectory() as temp_dir:
                self.status_update.emit("Extracting CBR archive...")

                if ext.lower() == '.cbr':
                    try:
                        if HAS_RAR:
                            with rarfile.RarFile(self.file_path, 'r') as rf:
                                files = rf.infolist()
                                for i, f in enumerate(files):
                                    rf.extract(f, temp_dir)
                                    self.progress_update.emit(i + 1, len(files))
                        else:
                            raise ImportError("rarfile not available")
                    except Exception:
                        patoolib.extract_archive(self.file_path, outdir=temp_dir, interactive=False)
                else:
                    self.finished_conversion.emit(False, "Unsupported format.", "")
                    return

                if self.xml_string:
                    self.status_update.emit("Generating metadata...")
                    xml_path = os.path.join(temp_dir, 'ComicInfo.xml')
                    with open(xml_path, 'w', encoding='utf-8') as f:
                        f.write(self.xml_string)

                self.status_update.emit("Creating new CBZ...")
                temp_cbz = new_cbz_path + ".tmp"

                all_files = []
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if file.lower() == 'comicinfo.xml' and root != temp_dir:
                            continue
                        all_files.append(os.path.join(root, file))

                with zipfile.ZipFile(temp_cbz, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for i, full_path in enumerate(all_files):
                        arcname = os.path.relpath(full_path, temp_dir)
                        zf.write(full_path, arcname)
                        self.progress_update.emit(i + 1, len(all_files))

                self.status_update.emit("Finalizing file...")
                os.replace(temp_cbz, new_cbz_path)

                if os.path.exists(self.file_path):
                    try:
                        os.remove(self.file_path)
                    except Exception as _e:
                        log.warning("Suppressed exception: %s", _e)
                self.finished_conversion.emit(True, "Successfully converted CBR and tagged!", new_cbz_path)

        except Exception as e:
            self.finished_conversion.emit(False, f"Error: {e}", "")


class NaturalSortProxyModel(QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hidden_paths = set()

    def filterAcceptsRow(self, source_row, source_parent):
        source_model = self.sourceModel()
        if hasattr(source_model, 'filePath'):
            index = source_model.index(source_row, 0, source_parent)
            path = os.path.normpath(source_model.filePath(index))
            if path in self.hidden_paths:
                return False
        return super().filterAcceptsRow(source_row, source_parent)

    def lessThan(self, source_left, source_right):
        source_model = self.sourceModel()
        left_data = source_model.data(source_left, Qt.ItemDataRole.DisplayRole)
        right_data = source_model.data(source_right, Qt.ItemDataRole.DisplayRole)

        left_str = str(left_data) if left_data is not None else ""
        right_str = str(right_data) if right_data is not None else ""

        if isinstance(source_model, QFileSystemModel):
            is_left_dir = source_model.isDir(source_left)
            is_right_dir = source_model.isDir(source_right)

            if is_left_dir and not is_right_dir:
                return True
            elif not is_left_dir and is_right_dir:
                return False

        return natural_sort_key(left_str) < natural_sort_key(right_str)


class FolderCoverLoaderThread(QThread):
    folder_cover_loaded = pyqtSignal(str, list)

    def __init__(self, folder_paths):
        super().__init__()
        self.folder_paths = folder_paths
        self.is_running = True

    def run(self):
        valid_exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')

        def try_zip(p):
            try:
                with zipfile.ZipFile(p, 'r') as zf:
                    names = zf.namelist()
                    images = [f for f in names if f.lower().endswith(valid_exts) and "__MACOSX" not in f and not os.path.basename(f).startswith('.')]
                    images.sort()
                    if images:
                        return zf.read(images[0])
            except Exception:
                pass
            return None

        def try_rar(p):
            if not HAS_RAR:
                return None
            try:
                with rarfile.RarFile(p, 'r') as rf:
                    names = rf.namelist()
                    images = [f for f in names if f.lower().endswith(valid_exts) and "__MACOSX" not in f and not os.path.basename(f).startswith('.')]
                    images.sort()
                    if images:
                        return rf.read(images[0])
            except Exception:
                pass
            return None

        for folder in self.folder_paths:
            if not self.is_running:
                break

            try:
                files = os.listdir(folder)
                comics = [f for f in files if f.lower().endswith(('.cbz', '.cbr'))]
                comics.sort(key=natural_sort_key)
                top_paths = [os.path.join(folder, c) for c in comics[:5]]

                if len(top_paths) < 5:
                    subdirs = [f for f in files if os.path.isdir(os.path.join(folder, f))]
                    subdirs.sort(key=natural_sort_key)
                    for subdir in subdirs:
                        if len(top_paths) >= 5:
                            break
                        sub_path = os.path.join(folder, subdir)
                        try:
                            sub_files = [f for f in os.listdir(sub_path) if f.lower().endswith(('.cbz', '.cbr'))]
                            if sub_files:
                                sub_files.sort(key=natural_sort_key)
                                top_paths.append(os.path.join(sub_path, sub_files[0]))
                        except Exception as _e:
                            log.warning("Suppressed exception: %s", _e)
                covers = []
                for p in top_paths:
                    if not self.is_running:
                        break

                    file_hash = hashlib.md5(os.path.normpath(p).encode('utf-8')).hexdigest()
                    custom_cache_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
                    standard_cache_path = os.path.join(CACHE_DIR, f"thumb_{file_hash}.jpg")

                    cover_bytes = None

                    if os.path.exists(custom_cache_path):
                        with open(custom_cache_path, 'rb') as f:
                            cover_bytes = f.read()
                    elif os.path.exists(standard_cache_path):
                        with open(standard_cache_path, 'rb') as f:
                            cover_bytes = f.read()
                    else:
                        if p.lower().endswith('.cbz'):
                            cover_bytes = try_zip(p)
                            if not cover_bytes:
                                cover_bytes = try_rar(p)
                        else:
                            cover_bytes = try_rar(p)
                            if not cover_bytes:
                                cover_bytes = try_zip(p)

                        if cover_bytes:
                            img = QImage()
                            if img.loadFromData(cover_bytes):
                                thumb = img.scaled(600, 900, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                thumb.save(standard_cache_path, "JPG", 88)

                                ba = QByteArray()
                                buf = QBuffer(ba)
                                buf.open(QIODevice.OpenModeFlag.WriteOnly)
                                thumb.save(buf, "JPG", 85)
                                cover_bytes = ba.data()
                            else:
                                try:
                                    with open(standard_cache_path, 'wb') as f:
                                        f.write(cover_bytes)
                                except Exception as _e:
                                    log.warning("Suppressed exception: %s", _e)
                    if cover_bytes:
                        covers.append(cover_bytes)

                self.folder_cover_loaded.emit(folder, covers)
            except Exception:
                self.folder_cover_loaded.emit(folder, [])

    def stop(self):
        self.is_running = False


class CoverLoaderThread(QThread):
    cover_loaded = pyqtSignal(str, bytes)

    def __init__(self, paths):
        super().__init__()
        self.paths = paths
        self.is_running = True

    def run(self):
        valid_exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')

        def try_zip(p):
            try:
                with zipfile.ZipFile(p, 'r') as zf:
                    names = zf.namelist()
                    images = [f for f in names if f.lower().endswith(valid_exts) and "__MACOSX" not in f and not os.path.basename(f).startswith('.')]
                    images.sort()
                    if images:
                        return zf.read(images[0])
            except Exception:
                pass
            return None

        def try_rar(p):
            if not HAS_RAR:
                return None
            try:
                with rarfile.RarFile(p, 'r') as rf:
                    names = rf.namelist()
                    images = [f for f in names if f.lower().endswith(valid_exts) and "__MACOSX" not in f and not os.path.basename(f).startswith('.')]
                    images.sort()
                    if images:
                        return rf.read(images[0])
            except Exception:
                pass
            return None

        for path in self.paths:
            if not self.is_running:
                break
            try:
                norm_p = os.path.normpath(path)
                file_hash = hashlib.md5(norm_p.encode('utf-8')).hexdigest()
                custom_cache_path = os.path.join(CACHE_DIR, f"custom_{file_hash}.jpg")
                standard_cache_path = os.path.join(CACHE_DIR, f"thumb_{file_hash}.jpg")

                if os.path.exists(custom_cache_path):
                    with open(custom_cache_path, 'rb') as f:
                        self.cover_loaded.emit(path, f.read())
                    continue

                if os.path.exists(standard_cache_path):
                    with open(standard_cache_path, 'rb') as f:
                        self.cover_loaded.emit(path, f.read())
                    continue

                cover_bytes = None
                if path.lower().endswith('.cbz'):
                    cover_bytes = try_zip(path)
                    if not cover_bytes:
                        cover_bytes = try_rar(path)
                else:
                    cover_bytes = try_rar(path)
                    if not cover_bytes:
                        cover_bytes = try_zip(path)

                if cover_bytes:
                    img = QImage()
                    if img.loadFromData(cover_bytes):
                        thumb = img.scaled(600, 900, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        thumb.save(standard_cache_path, "JPG", 88)
                        ba = QByteArray()
                        buf = QBuffer(ba)
                        buf.open(QIODevice.OpenModeFlag.WriteOnly)
                        thumb.save(buf, "JPG", 88)
                        cover_bytes = ba.data()
                    else:
                        try:
                            with open(standard_cache_path, 'wb') as f:
                                f.write(cover_bytes)
                        except Exception as _e:
                            log.warning("Suppressed exception: %s", _e)
                self.cover_loaded.emit(path, cover_bytes if cover_bytes else b'')

            except Exception:
                self.cover_loaded.emit(path, b'')

    def stop(self):
        self.is_running = False


class ComicVineSearchThread(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        headers = {"User-Agent": "ComicVault/1.0"}
        encoded = urllib.parse.quote(self.query)
        combined = {}
        try:
            filter_url = (
                f"https://comicvine.gamespot.com/api/volumes/"
                f"?api_key={COMIC_VINE_KEY}&format=json"
                f"&filter=name:{encoded}&limit=50"
                f"&field_list=id,name,start_year,publisher,count_of_issues,image,api_detail_url"
            )
            r1 = requests.get(filter_url, headers=headers, timeout=10).json()
            if r1.get('error') == 'OK':
                for v in r1.get('results', []):
                    combined[v['id']] = v

            time.sleep(0.5)

            search_url = (
                f"https://comicvine.gamespot.com/api/search/"
                f"?api_key={COMIC_VINE_KEY}&format=json"
                f"&resources=volume&query={encoded}&limit=25"
            )
            r2 = requests.get(search_url, headers=headers, timeout=10).json()
            if r2.get('error') == 'OK':
                for v in r2.get('results', []):
                    combined[v['id']] = v

            for _the_variant in _the_variants(self.query)[1:]:
                if _the_variant.lower() != self.query.lower():
                    time.sleep(0.4)
                    _tq = urllib.parse.quote(_the_variant)
                    _tr = requests.get(
                        f"https://comicvine.gamespot.com/api/volumes/"
                        f"?api_key={COMIC_VINE_KEY}&format=json"
                        f"&filter=name:{_tq}&limit=20"
                        f"&field_list=id,name,start_year,publisher,count_of_issues,image,api_detail_url",
                        headers=headers, timeout=10
                    ).json()
                    if _tr.get('error') == 'OK':
                        for v in _tr.get('results', []):
                            combined[v['id']] = v

        except Exception as _e:
            log.warning("ComicVineSearchThread failed: %s", _e)

        results = list(combined.values())
        results.sort(key=lambda x: (
            -int(x.get('count_of_issues') or 0),
            int(re.search(r'\d+', str(x.get('start_year', 9999))).group())
            if re.search(r'\d+', str(x.get('start_year', 9999))) else 9999
        ))
        self.results_ready.emit(results)


class ComicVineIssueSearchThread(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, query):
        super().__init__()
        self.query = query.strip()

    def run(self):
        headers = {"User-Agent": "YourComicsApp/1.0"}

        parsed = parse_comic_filename_full(self.query)
        series = parsed['series']
        issue = parsed['issue']
        year_str = parsed['year']
        subtitle = parsed['subtitle']
        vol_num = parsed['vol_num']

        if not series:
            series = self.query
            issue = ""
            year_str = ""
            subtitle = ""
            vol_num = ""

        final_results = []
        target_vol_id = None

        try:
            vol_query = urllib.parse.quote(series)
            vol_combined = {}

            filter_url = (
                f"https://comicvine.gamespot.com/api/volumes/"
                f"?api_key={COMIC_VINE_KEY}&format=json"
                f"&filter=name:{vol_query}&limit=30"
                f"&field_list=id,name,start_year,count_of_issues,publisher,api_detail_url"
            )
            time.sleep(1.5)
            r1 = requests.get(filter_url, headers=headers, timeout=10).json()
            if r1.get('error') == 'OK':
                for v in r1.get('results', []):
                    vol_combined[v['id']] = v

            time.sleep(1.0)

            search_url = (
                f"https://comicvine.gamespot.com/api/search/"
                f"?api_key={COMIC_VINE_KEY}&format=json"
                f"&resources=volume&query={vol_query}&limit=20"
            )
            r2 = requests.get(search_url, headers=headers, timeout=10).json()
            if r2.get('error') == 'OK':
                for v in r2.get('results', []):
                    vol_combined[v['id']] = v

            for _the_variant in _the_variants(series)[1:]:
                if _the_variant.lower() != series.lower():
                    time.sleep(0.5)
                    _tq = urllib.parse.quote(_the_variant)
                    _tr = requests.get(
                        f"https://comicvine.gamespot.com/api/volumes/"
                        f"?api_key={COMIC_VINE_KEY}&format=json"
                        f"&filter=name:{_tq}&limit=20"
                        f"&field_list=id,name,start_year,count_of_issues,publisher,api_detail_url",
                        headers=headers, timeout=10
                    ).json()
                    if _tr.get('error') == 'OK':
                        for v in _tr.get('results', []):
                            vol_combined[v['id']] = v

            if subtitle:
                time.sleep(1.0)
                full_query = urllib.parse.quote(f"{series} {subtitle}")
                r3 = requests.get(
                    f"https://comicvine.gamespot.com/api/search/"
                    f"?api_key={COMIC_VINE_KEY}&format=json"
                    f"&resources=volume&query={full_query}&limit=10",
                    headers=headers, timeout=10
                ).json()
                if r3.get('error') == 'OK':
                    for v in r3.get('results', []):
                        vol_combined[v['id']] = v
                for extra_kw in ('deluxe', 'omnibus'):
                    triggers = [
                        re.match(r'(?i)^book\s*\d+$', subtitle),
                        extra_kw in subtitle.lower(),
                    ]
                    if any(triggers):
                        time.sleep(0.8)
                        eq = urllib.parse.quote(f"{series} {extra_kw}")
                        r4 = requests.get(
                            f"https://comicvine.gamespot.com/api/search/"
                            f"?api_key={COMIC_VINE_KEY}&format=json"
                            f"&resources=volume&query={eq}&limit=10",
                            headers=headers, timeout=10
                        ).json()
                        if r4.get('error') == 'OK':
                            for v in r4.get('results', []):
                                vol_combined[v['id']] = v

            vol_results = list(vol_combined.values())
            if vol_results:
                vol_results.sort(
                    key=lambda v: _score_volume(v, series, issue, year_str, subtitle, vol_num),
                    reverse=True
                )
                target_vol_id = vol_results[0]['id']

            if target_vol_id:
                issue_filter = f"volume:{target_vol_id}"
                if issue:
                    issue_filter += f",issue_number:{issue}"

                issue_url = f"https://comicvine.gamespot.com/api/issues/?api_key={COMIC_VINE_KEY}&format=json&filter={urllib.parse.quote(issue_filter)}&field_list=id,name,issue_number,cover_date,volume,api_detail_url,page_count,image,language"

                time.sleep(1.5)
                issue_response = requests.get(issue_url, headers=headers, timeout=10)
                issue_data = issue_response.json()

                if issue_data.get('error') == 'OK' and issue_data.get('number_of_total_results', 0) > 0:
                    final_results = issue_data['results']

            if parsed.get('is_tpb'):
                tpb_query = urllib.parse.quote(
                    f"{series} {subtitle}".strip() if subtitle else series
                )
                tpb_url = f"https://comicvine.gamespot.com/api/search/?api_key={COMIC_VINE_KEY}&format=json&resources=issue&query={tpb_query}&limit=15&field_list=id,name,issue_number,cover_date,volume,api_detail_url,page_count,image,language"
                time.sleep(1.5)
                r3 = requests.get(tpb_url, headers=headers, timeout=10).json()
                if r3.get('error') == 'OK':
                    existing_ids = {r['id'] for r in final_results}
                    for r in r3.get('results', []):
                        if r['id'] not in existing_ids:
                            final_results.append(r)
            elif not final_results:
                search_url = f"https://comicvine.gamespot.com/api/search/?api_key={COMIC_VINE_KEY}&format=json&resources=issue&query={urllib.parse.quote(self.query)}&limit=10&field_list=id,name,issue_number,cover_date,volume,api_detail_url,page_count,image,language"
                time.sleep(1.5)
                response = requests.get(search_url, headers=headers, timeout=10)
                fuzzy_data = response.json()
                if fuzzy_data.get('error') == 'OK':
                    existing_ids = {r['id'] for r in final_results}
                    for r in fuzzy_data.get('results', []):
                        if r['id'] not in existing_ids:
                            final_results.append(r)

        except Exception as e:
            log.warning("Manual Search Error: %s", e)

        def _score_issue(r):
            score = 0
            vol = r.get('volume', {}) or {}
            vol_name = str(vol.get('name') or '').lower()
            issue_name = str(r.get('name') or '').lower()
            issue_num = str(r.get('issue_number') or '')

            lang = str(r.get('language') or '').lower()
            if lang and lang != 'english':
                score -= 80

            _vn = _norm_vol_name(vol_name)
            _wn = _norm_vol_name(series)
            if _vn and _vn == _wn:
                score += 50
            elif _wn and _wn in _vn:
                score += 25
            elif _wn and _vn in _wn:
                score += 15
            if year_str:
                result_year = str(r.get('cover_date', ''))[:4]
                if result_year == year_str:
                    score += 25
                elif result_year and result_year != year_str:
                    score -= 20

            if parsed.get('is_tpb'):
                if target_vol_id and str(vol.get('id', '')) == str(target_vol_id):
                    score += 30
                if re.search(r'\bvol\.?\s*\d', issue_name, re.I):
                    score += 200
                if subtitle and subtitle.lower() in issue_name:
                    score += 150
                if vol_num and issue_num == vol_num:
                    score += 100
                try:
                    if int(r.get('page_count') or 0) > 100:
                        score += 120
                except (ValueError, TypeError):
                    pass
                try:
                    n = int(issue_num)
                    if n > 50:
                        score -= 80
                    elif n > 20:
                        score -= 40
                except (ValueError, TypeError):
                    pass
            else:
                if target_vol_id and str(vol.get('id', '')) == str(target_vol_id):
                    score += 60
                if issue and issue_num == issue:
                    score += 80
                if subtitle and subtitle.lower() in issue_name:
                    score += 40

            return score

        final_results.sort(key=_score_issue, reverse=True)
        self.results_ready.emit(final_results)


class ImageDownloadThread(QThread):
    image_ready = pyqtSignal(bytes)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            res = requests.get(self.url, headers={"User-Agent": "ComicVault/1.0"})
            self.image_ready.emit(res.content)
        except Exception:
            self.image_ready.emit(b"")


class MetadataInjectorThread(QThread):
    success = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, filepath, xml_string):
        super().__init__()
        self.filepath = filepath
        self.xml_string = xml_string

    def run(self):
        target_dir = os.path.dirname(self.filepath)
        base_name = os.path.basename(self.filepath)
        name_no_ext, ext = os.path.splitext(base_name)
        ext = ext.lower()

        if ext == '.cbz':
            try:
                inject_metadata_into_cbz(self.filepath, self.xml_string)
                self.success.emit("Metadata injected successfully!", self.filepath)
            except PermissionError:
                for attempt in range(4):
                    try:
                        time.sleep(0.5)
                        inject_metadata_into_cbz(self.filepath, self.xml_string)
                        self.success.emit("Metadata injected successfully!", self.filepath)
                        return
                    except PermissionError:
                        pass
                self.error.emit("Failed to inject metadata: file is locked.")
            except Exception as e:
                log.warning("MetadataInjectorThread CBZ failed: %s", e)
                self.error.emit(f"Failed to inject metadata:\n{e}")

        elif ext == '.cbr':
            new_cbz_path = os.path.join(target_dir, f"{name_no_ext}.cbz")
            temp_path = os.path.join(target_dir, f".temp_{name_no_ext}.cbz")

            try:
                if HAS_RAR:
                    with rarfile.RarFile(self.filepath, 'r') as rin:
                        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                            for item in rin.infolist():
                                if not item.isdir() and item.filename.lower() != 'comicinfo.xml':
                                    zout.writestr(item.filename, rin.read(item))
                            zout.writestr('ComicInfo.xml', self.xml_string.encode('utf-8'))
                else:
                    temp_dir = tempfile.mkdtemp()
                    try:
                        patoolib.extract_archive(self.filepath, outdir=temp_dir, interactive=False)
                        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                            for root, _, files in os.walk(temp_dir):
                                for f in files:
                                    if f.lower() == 'comicinfo.xml':
                                        continue
                                    fp = os.path.join(root, f)
                                    zout.write(fp, os.path.relpath(fp, temp_dir))
                            zout.writestr('ComicInfo.xml', self.xml_string.encode('utf-8'))
                    finally:
                        shutil.rmtree(temp_dir, onerror=force_remove_readonly)

                for attempt in range(5):
                    try:
                        os.replace(temp_path, new_cbz_path)
                        try:
                            os.remove(self.filepath)
                        except Exception as _e:
                            log.warning("Suppressed exception: %s", _e)
                        self.success.emit("Converted CBR to CBZ & Injected Metadata!", new_cbz_path)
                        return
                    except PermissionError as e:
                        if attempt < 4:
                            time.sleep(0.5)
                        else:
                            raise e
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                self.error.emit(f"Failed to convert CBR to CBZ:\n{e}")


class GeminiSummaryThread(QThread):
    summary_ready = pyqtSignal(str)

    def __init__(self, issue_data, series_name, issue_num, alt_name=""):
        super().__init__()
        self.issue_data = issue_data
        self.series_name = series_name
        self.issue_num = issue_num
        self.alt_name = alt_name
        self.ai_client = genai.Client(api_key=GEMINI_KEY)

    def run(self):
        chars = ", ".join([c['name'] for c in (self.issue_data.get('character_credits') or [])])
        plot = str(self.issue_data.get('description') or self.issue_data.get('deck') or "")[:5000]
        needs_search = len(plot.strip()) < 50
        base_title = self.series_name.split(' (')[0]
        search_target = f"{base_title} {self.alt_name} issue {self.issue_num}" if self.alt_name else f"{self.series_name} issue {self.issue_num}"
        prompt = f"Expert comic historian. Write 500-800 word deep-dive into {self.series_name} #{self.issue_num}."
        if needs_search:
            prompt += f"\nUSE GOOGLE SEARCH for: '{search_target}'. Only summarize issue #{self.issue_num} specifically."
        else:
            prompt += f"\nPLOT: {plot}"
        prompt += f"\nCharacters: {chars}\nHeadings: Context, Detailed Plot, Key Moments, Significance."

        try:
            from google.genai import types
            cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())] if needs_search else None)
            resp = self.ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=cfg)
            self.summary_ready.emit(resp.text)
        except Exception as e:
            self.summary_ready.emit(f"Error generating summary: {str(e)}")


class GeminiChatThread(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, context_summary, history, user_text):
        super().__init__()
        self.context_summary = context_summary
        self.history = history
        self.user_text = user_text

    def run(self):
        if not GEMINI_KEY:
            self.error_occurred.emit("Missing Gemini API Key!")
            return

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_KEY)

            prompt = "You are a helpful comic book expert AI.\n\n"

            if self.context_summary:
                prompt += f"Context about the currently selected comic:\n{self.context_summary}\n\n"

            prompt += "Conversation History:\n"
            for msg in self.history:
                role = "User" if msg.get("role") == "user" else "AI"
                prompt += f"{role}: {msg.get('content')}\n"

            chat_config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=chat_config
            )

            self.response_ready.emit(response.text)

        except Exception as e:
            self.error_occurred.emit(f"AI Error: {str(e)}")


class TTSWorkerThread(QThread):
    audio_ready = pyqtSignal(bytes)

    def __init__(self, text, voice):
        super().__init__()
        self.text = text
        self.voice = voice

    async def _generate_audio(self):
        audio_bytes = bytearray()
        sentences = self.text.split('.')

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            chunk_text = sentence + "."
            communicate = edge_tts.Communicate(chunk_text, self.voice)

            async for chunk_data in communicate.stream():
                if chunk_data["type"] == "audio":
                    audio_bytes.extend(chunk_data["data"])
        return bytes(audio_bytes)

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            final_audio_bytes = loop.run_until_complete(self._generate_audio())
            self.audio_ready.emit(final_audio_bytes)

        except Exception as e:
            log.warning("TTS Engine Failed: %s", e)
        finally:
            loop.close()


class BatchProcessorThread(QThread):
    progress_update = pyqtSignal(int, int)
    log_update = pyqtSignal(str)
    finished_batch = pyqtSignal(str)

    def __init__(self, vol_id, vol_name, alt_name, start_issue, end_issue, output_dir):
        super().__init__()
        self.vol_id = vol_id
        self.vol_name = vol_name
        self.alt_name = alt_name
        self.start_issue = start_issue
        self.end_issue = end_issue
        self.output_dir = output_dir
        self._is_running = True
        self.ai_client = genai.Client(api_key=GEMINI_KEY)

    def run(self):
        total = self.end_issue - self.start_issue + 1
        for i, curr_issue in enumerate(range(self.start_issue, self.end_issue + 1)):
            if not self._is_running:
                break
            self.log_update.emit(f"Processing #{curr_issue}...")

            url = f"https://comicvine.gamespot.com/api/issues/?api_key={COMIC_VINE_KEY}&format=json"
            params = {
                "api_key": COMIC_VINE_KEY,
                "format": "json",
                "filter": f"volume:{self.vol_id},issue_number:{curr_issue}",
                "field_list": "name,deck,description,character_credits,person_credits,team_credits,location_credits,story_arc_credits,image,cover_date,issue_number,volume,page_count,site_detail_url,rating,format"
            }
            try:
                res = requests.get(url, params=params, headers={"User-Agent": "ComicVault/1.0"}).json()
                b_data = res.get('results', [])[0] if res.get('results') else None
            except Exception as e:
                self.log_update.emit(f"Error fetching #{curr_issue}: {e}")
                continue

            if not b_data:
                self.log_update.emit(f"Issue #{curr_issue} not found. Skipping.")
                self.progress_update.emit(i + 1, total)
                continue

            chars = ", ".join([c['name'] for c in (b_data.get('character_credits') or [])])
            plot = str(b_data.get('description') or b_data.get('deck') or "")[:5000]
            needs_search = len(plot.strip()) < 50
            base_title = self.vol_name.split(' (')[0]
            search_target = f"{base_title} {self.alt_name} issue {curr_issue}" if self.alt_name else f"{self.vol_name} issue {curr_issue}"

            prompt = f"Expert comic historian. Write 500-800 word deep-dive into {self.vol_name} #{curr_issue}."
            if needs_search:
                prompt += f"\nUSE GOOGLE SEARCH for: '{search_target}'. Only summarize issue #{curr_issue} specifically."
            else:
                prompt += f"\nPLOT: {plot}"
            prompt += f"\nCharacters: {chars}\nHeadings: Context, Detailed Plot, Key Moments, Significance."

            b_sum = "Error generating summary."
            models = ["gemini-2.5-flash", "gemini-3.1-pro-preview"]
            for m in models:
                wait = 5
                success = False
                for att in range(2):
                    if not self._is_running:
                        break
                    try:
                        from google.genai import types
                        cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())] if needs_search else None)
                        resp = self.ai_client.models.generate_content(model=m, contents=prompt, config=cfg)
                        b_sum = resp.text
                        success = True
                        break
                    except Exception:
                        time.sleep(wait + random.uniform(1, 2))
                        wait *= 2
                if success:
                    break

            try:
                cover_url = b_data.get('image', {}).get('medium_url')
                title = f"{self.vol_name} #{curr_issue}"

                book = epub.EpubBook()
                book.set_identifier(title.replace(" ", "_").replace("#", ""))
                book.set_title(title)
                book.set_language('en')
                book.add_author("Comic Vault Analyzer")

                if cover_url:
                    try:
                        img_data = requests.get(cover_url).content
                        book.set_cover("cover.jpg", img_data)
                    except Exception as _e:
                        log.warning("Suppressed exception: %s", _e)
                c1 = epub.EpubHtml(title=title, file_name='chap_01.xhtml', lang='en')
                c1.content = f'<h2>{title}</h2>' + markdown.markdown(b_sum)
                book.add_item(c1)
                book.toc = (epub.Link('chap_01.xhtml', title, 'intro'),)
                book.add_item(epub.EpubNcx())
                book.add_item(epub.EpubNav())
                book.spine = ['nav', c1]

                clean_vol = self.vol_name.replace(' ', '_').replace('/', '_')
                out_path = os.path.join(self.output_dir, f"{clean_vol}_{curr_issue}.epub")
                epub.write_epub(out_path, book)
            except Exception as e:
                self.log_update.emit(f"Error saving EPUB #{curr_issue}: {e}")

            self.progress_update.emit(i + 1, total)
            time.sleep(random.uniform(3, 5))

        self.finished_batch.emit(self.output_dir)

    def stop(self):
        self._is_running = False


class AIListGeneratorThread(QThread):
    list_ready = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        if not GEMINI_KEY:
            self.error_signal.emit("Missing Gemini API Key!")
            return

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_KEY)

            prompt = (
                f'You are a comic book historian. Create a chronological reading order list for: "{self.query}".\n'
                "USE GOOGLE SEARCH to ensure the reading order is accurate, canon, and COMPLETE.\n\n"
                "CRITICAL INSTRUCTION FOR LONG LISTS: You MUST be EXHAUSTIVE. Do NOT truncate, abbreviate, or summarize the list. If there are dozens or hundreds of items, you must list EVERY SINGLE ONE.\n\n"
                "CRITICAL INSTRUCTION FOR COLLECTIONS/TPBs/OMNIBUSES:\n"
                "If the item is a Trade Paperback, Graphic Novel, Omnibus, or Collection, DO NOT put a number in the 'issue' field. Put the full title (including Volume numbers) in the 'series' field, and leave the 'issue' field completely BLANK (e.g. \"\").\n\n"
                "You MUST return ONLY a raw JSON dictionary. Do not include markdown formatting.\n"
                "The JSON must use these exact keys: 'description' and 'items'.\n"
                "The 'description' should be a brief 2-3 sentence explanation of the reading order you compiled, explaining the scope and what is included.\n"
                "The 'items' key must contain an array of objects with the keys: 'series', 'issue', and 'year'.\n\n"
                "Example Format:\n"
                "{\n"
                '  "description": "This is the complete Marvel Civil War main event reading order, including the main 7 issues and essential tie-ins like Amazing Spider-Man.",\n'
                '  "items": [\n'
                '    {"series": "The Amazing Spider-Man", "issue": "529", "year": "2006"},\n'
                '    {"series": "Civil War", "issue": "1", "year": "2006"}\n'
                '  ]\n'
                "}\n"
            )

            config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)

            text = response.text.strip()

            bt = chr(96) * 3
            if text.startswith(bt + "json"):
                text = text[7:].strip()
            elif text.startswith(bt):
                text = text[3:].strip()
            if text.endswith(bt):
                text = text[:-3].strip()

            ai_data = json.loads(text)
            self.list_ready.emit(ai_data)

        except Exception as e:
            self.error_signal.emit(str(e))


class DeepSearchThread(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, query, libraries):
        super().__init__()
        self.query = query.lower()
        self.libraries = libraries

    def run(self):
        results = []
        for lib in self.libraries:
            if not os.path.exists(lib):
                continue
            for root, dirs, files in os.walk(lib):
                for d in dirs:
                    if self.query in d.lower():
                        results.append({"name": d, "path": os.path.join(root, d), "is_folder": True})
                for f in files:
                    if f.lower().endswith(('.cbz', '.cbr', '.cbl')) and self.query in f.lower():
                        results.append({"name": f, "path": os.path.join(root, f), "is_folder": False})
        self.results_ready.emit(results)


class GithubCBLFetchThread(QThread):
    results_ready = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    BASE = "https://api.github.com/repos/DieselTech/CBL-ReadingLists/contents/"

    def __init__(self, path=""):
        super().__init__()
        self.path = path

    def run(self):
        try:
            url = self.BASE + urllib.parse.quote(self.path, safe="/")
            resp = requests.get(url, headers={"User-Agent": "ComicVault/1.0"}, timeout=10)
            resp.raise_for_status()
            items = resp.json()
            results = []
            for item in items:
                if item.get("type") in ("dir", "file"):
                    name = item["name"]
                    if item["type"] == "file" and not name.lower().endswith(".cbl"):
                        continue
                    if name.startswith("."):
                        continue
                    results.append({
                        "name": name,
                        "path": item["path"],
                        "type": item["type"],
                        "download_url": item.get("download_url") or "",
                    })
            results.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
            self.results_ready.emit(results)
        except Exception as e:
            self.error_signal.emit(str(e))


class GithubCBLDownloadThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, download_url: str, save_path: str):
        super().__init__()
        self.download_url = download_url
        self.save_path = save_path

    def run(self):
        try:
            resp = requests.get(
                self.download_url,
                headers={"User-Agent": "ComicVault/1.0"},
                timeout=15,
            )
            resp.raise_for_status()
            with open(self.save_path, "wb") as f:
                f.write(resp.content)
            self.finished.emit(self.save_path)
        except Exception as e:
            self.error.emit(str(e))


class GetComicsCheckThread(QThread):
    results_ready = pyqtSignal(dict)

    def __init__(self, followed):
        super().__init__()
        self.followed = followed

    def run(self):
        found = {}
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/123.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        })
        try:
            session.get("https://getcomics.org/", timeout=10)
            time.sleep(0.5)
        except Exception:
            pass

        for item in self.followed:
            if not self.isRunning():
                break
            vid = item.get("vol_id", "")
            title = item.get("title", "")
            if not title:
                found[vid] = ""
                continue
            try:
                q = urllib.parse.quote(title)
                resp = session.get(f"https://getcomics.org/search/{q}/", timeout=12)
                html = resp.content.decode("utf-8", errors="replace")
                url = _gc_first_article(html)
                log.warning("GC [%d] '%s' → %s", resp.status_code, title, url or "NOT FOUND")
                if not url:
                    log.warning("GC snippet: %s", html[200:1200].replace('\n', ' '))
                found[vid] = url
            except Exception as _e:
                log.warning("GC check error '%s': %s", title, _e)
                found[vid] = ""
            time.sleep(1.5)
        self.results_ready.emit(found)


class GCSitemapThread(QThread):
    results_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, week_start):
        super().__init__()
        self.week_start = week_start

    def run(self):
        try:
            hdrs = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0",
                "Accept-Language": "en-US,en;q=0.9",
            }
            resp = requests.get("https://getcomics.org/sitemap/", headers=hdrs, timeout=15)
            html = resp.content.decode("utf-8", errors="replace")

            week_end = self.week_start + _dt.timedelta(days=7)
            groups = {"dc": [], "marvel": [], "other": []}
            seen_urls = set()
            seen_titles = set()

            def _publisher_bucket(section: str, title: str) -> str:
                s = (section or "").lower().strip()
                t = (title or "").lower()
                if s in ("dc", "dc-comics", "dccomics"):
                    return "dc"
                if s in ("marvel", "marvel-comics", "marvelcomics"):
                    return "marvel"
                # Fallback by title for misfiled posts (e.g., The Flash under other)
                if re.search(r"\b(dc|flash|the flash|absolute flash|batman|superman|wonder woman|green lantern|nightwing|titans|justice league)\b", t):
                    return "dc"
                if re.search(r"\b(marvel|spider-man|avengers|x-men|wolverine|deadpool|fantastic four|daredevil)\b", t):
                    return "marvel"
                return "other"

            for m in re.finditer(
                r'href="(https://getcomics\.org/([^/]+)/([^"]+)/)"[^>]*>([^<]+)</a>\s*([A-Za-z]+ \d+, \d{4})',
                html, re.DOTALL
            ):
                url = m.group(1)
                section = m.group(2).lower()
                title = m.group(4).strip()
                date_str = m.group(5).strip()

                try:
                    post_date = _dt.datetime.strptime(date_str, "%B %d, %Y").date()
                except ValueError:
                    continue

                if not (self.week_start <= post_date < week_end):
                    continue

                title_clean = _html_mod.unescape(title).strip()
                url_norm = url.strip().rstrip("/")
                title_norm = re.sub(r"\s+", " ", title_clean.lower())

                # Deduplicate repeated sitemap entries / mirrors.
                if url_norm in seen_urls or title_norm in seen_titles:
                    continue
                seen_urls.add(url_norm)
                seen_titles.add(title_norm)

                entry = {"title": title_clean, "url": url, "date": date_str}
                groups[_publisher_bucket(section, title_clean)].append(entry)

            self.results_ready.emit(groups)
        except Exception as e:
            self.error_occurred.emit(str(e))


class GCCoverThread(QThread):
    cover_ready = pyqtSignal(str, bytes)

    def __init__(self, entries):
        super().__init__()
        self.entries = entries
        self.is_running = True

    def run(self):
        hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0"}
        for entry in self.entries:
            if not self.is_running:
                break
            url = entry.get("url", "")
            try:
                resp = requests.get(url, headers=hdrs, timeout=10)
                html = resp.content.decode("utf-8", errors="replace")
                img_url = ""
                # Support property/name ordering, single quotes, and common fallbacks.
                patterns = [
                    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                    r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
                ]
                for pat in patterns:
                    m = re.search(pat, html, flags=re.IGNORECASE)
                    if m:
                        img_url = m.group(1)
                        break
                if img_url:
                    img_resp = requests.get(img_url, headers=hdrs, timeout=10)
                    self.cover_ready.emit(url, img_resp.content)
                else:
                    self.cover_ready.emit(url, b"")
            except Exception:
                self.cover_ready.emit(url, b"")
            time.sleep(0.4)

    def stop(self):
        self.is_running = False


class BatchTaggerThread(QThread):
    progress_update = pyqtSignal(int, str)
    finished = pyqtSignal()
    needs_confirmation = pyqtSignal(str, object, bytes)
    matches_collected = pyqtSignal(list)

    def __init__(self, file_paths, interactive=True, overwrite=False, vol_urls="", ai_summaries=False):
        super().__init__()
        self.file_paths = file_paths
        self.interactive = interactive
        self.overwrite_meta = overwrite
        self.vol_urls = vol_urls
        self.ai_summaries = ai_summaries
        self.user_choice = None
        self.wait_event = threading.Event()
        self._is_running = True
        self._auto_matches = []

    def stop(self):
        self._is_running = False
        self.wait_event.set()

    def run(self):
        headers = {"User-Agent": "YourComicsApp/1.0"}
        forced_vol_ids = re.findall(r'4050-(\d+)', self.vol_urls)

        for i, path in enumerate(self.file_paths):
            if not self._is_running:
                self.progress_update.emit(i, "🛑 Batch Tagging Cancelled by User!")
                break

            filename = os.path.basename(path)
            is_cbr = path.lower().endswith('.cbr')

            if not is_cbr and not self.overwrite_meta:
                try:
                    with zipfile.ZipFile(path, 'r') as zf:
                        if 'ComicInfo.xml' in zf.namelist():
                            self.progress_update.emit(i, f"⏭️ Skipped {filename} (Already has metadata)")
                            continue
                except Exception:
                    pass

            base_name = os.path.splitext(filename)[0]
            parsed = parse_comic_filename_full(base_name)
            series = parsed['series']
            issue = parsed['issue']
            vol_num = parsed['vol_num']
            subtitle = parsed['subtitle']
            year_str = parsed['year']
            is_tpb = parsed['is_tpb']

            if is_tpb and subtitle:
                search_text = f"{series} {subtitle} {year_str}".strip()
            else:
                search_text = f"{series} {issue} {year_str}".strip()

            try:
                target_vol_id = None
                data = {'error': 'Failed', 'results': [], 'number_of_total_results': 0}

                if forced_vol_ids:
                    for vid in forced_vol_ids:
                        self.progress_update.emit(i, f"🔍 Checking Forced Volume {vid} for Issue #{issue}...")
                        issue_filter = f"volume:{vid}"
                        if issue:
                            issue_filter += f",issue_number:{issue}"

                        issue_url = f"https://comicvine.gamespot.com/api/issues/?api_key={COMIC_VINE_KEY}&format=json&filter={urllib.parse.quote(issue_filter)}&field_list=id,name,issue_number,cover_date,volume,api_detail_url,page_count,image,language"
                        time.sleep(1.5)
                        issue_response = requests.get(issue_url, headers=headers, timeout=10)
                        issue_data = issue_response.json()

                        if issue_data.get('error') == 'OK' and issue_data.get('number_of_total_results', 0) > 0:
                            data = issue_data
                            target_vol_id = vid
                            break

                if not target_vol_id and not forced_vol_ids:
                    self.progress_update.emit(i, f"🔍 Searching Vine: {search_text}...")
                    vol_query = urllib.parse.quote(series)
                    vol_combined = {}

                    filter_url = (
                        f"https://comicvine.gamespot.com/api/volumes/"
                        f"?api_key={COMIC_VINE_KEY}&format=json"
                        f"&filter=name:{vol_query}&limit=30"
                        f"&field_list=id,name,start_year,count_of_issues,publisher,api_detail_url"
                    )
                    time.sleep(1.5)
                    r1 = requests.get(filter_url, headers=headers, timeout=10).json()
                    if r1.get('error') == 'OK':
                        for v in r1.get('results', []):
                            vol_combined[v['id']] = v

                    time.sleep(1.0)

                    search_vol_url = (
                        f"https://comicvine.gamespot.com/api/search/"
                        f"?api_key={COMIC_VINE_KEY}&format=json"
                        f"&resources=volume&query={vol_query}&limit=20"
                    )
                    r2 = requests.get(search_vol_url, headers=headers, timeout=10).json()
                    if r2.get('error') == 'OK':
                        for v in r2.get('results', []):
                            vol_combined[v['id']] = v

                    for _the_variant in _the_variants(series)[1:]:
                        if _the_variant.lower() != series.lower():
                            time.sleep(0.5)
                            _tq = urllib.parse.quote(_the_variant)
                            _tr = requests.get(
                                f"https://comicvine.gamespot.com/api/volumes/"
                                f"?api_key={COMIC_VINE_KEY}&format=json"
                                f"&filter=name:{_tq}&limit=20"
                                f"&field_list=id,name,start_year,count_of_issues,publisher,api_detail_url",
                                headers=headers, timeout=10
                            ).json()
                            if _tr.get('error') == 'OK':
                                for v in _tr.get('results', []):
                                    vol_combined[v['id']] = v

                    if is_tpb and subtitle:
                        time.sleep(1.0)
                        full_query = urllib.parse.quote(f"{series} {subtitle}")
                        r3 = requests.get(
                            f"https://comicvine.gamespot.com/api/search/"
                            f"?api_key={COMIC_VINE_KEY}&format=json"
                            f"&resources=volume&query={full_query}&limit=10",
                            headers=headers, timeout=10
                        ).json()
                        if r3.get('error') == 'OK':
                            for v in r3.get('results', []):
                                vol_combined[v['id']] = v
                        for extra_kw in ('deluxe', 'omnibus'):
                            triggers = [
                                re.match(r'(?i)^book\s*\d+$', subtitle),
                                extra_kw in subtitle.lower(),
                            ]
                            if any(triggers):
                                time.sleep(0.8)
                                eq = urllib.parse.quote(f"{series} {extra_kw}")
                                r4 = requests.get(
                                    f"https://comicvine.gamespot.com/api/search/"
                                    f"?api_key={COMIC_VINE_KEY}&format=json"
                                    f"&resources=volume&query={eq}&limit=10",
                                    headers=headers, timeout=10
                                ).json()
                                if r4.get('error') == 'OK':
                                    for v in r4.get('results', []):
                                        vol_combined[v['id']] = v

                    vol_results = list(vol_combined.values())
                    if vol_results:
                        vol_results.sort(
                            key=lambda v: _score_volume(v, series, issue, year_str, subtitle, vol_num),
                            reverse=True
                        )
                        target_vol_id = vol_results[0]['id']

                if target_vol_id and data.get('number_of_total_results', 0) == 0:
                    self.progress_update.emit(i, f"🎯 Volume matched! Fetching Issue #{issue}...")
                    issue_filter = f"volume:{target_vol_id}"
                    if issue:
                        issue_filter += f",issue_number:{issue}"
                    issue_url = f"https://comicvine.gamespot.com/api/issues/?api_key={COMIC_VINE_KEY}&format=json&filter={urllib.parse.quote(issue_filter)}&field_list=id,name,issue_number,cover_date,volume,api_detail_url,page_count,image,language"

                    time.sleep(1.5)
                    issue_response = requests.get(issue_url, headers=headers, timeout=10)
                    issue_data = issue_response.json()

                    if issue_data.get('error') == 'OK' and issue_data.get('number_of_total_results', 0) > 0:
                        data = issue_data

                step2_found = data.get('number_of_total_results', 0) > 0

                if is_tpb:
                    tpb_query = urllib.parse.quote(
                        f"{series} {subtitle}".strip() if subtitle else series
                    )
                    search_url = f"https://comicvine.gamespot.com/api/search/?api_key={COMIC_VINE_KEY}&format=json&resources=issue&query={tpb_query}&limit=15&field_list=id,name,issue_number,cover_date,volume,api_detail_url,page_count,image,language"
                    time.sleep(1.5)
                    response = requests.get(search_url, headers=headers, timeout=10)
                    fuzzy_data = response.json()
                    if fuzzy_data.get('error') == 'OK':
                        existing_ids = {r['id'] for r in data.get('results', [])}
                        for r in fuzzy_data.get('results', []):
                            if r['id'] not in existing_ids:
                                data['results'].append(r)
                        data['number_of_total_results'] = len(data['results'])
                elif not step2_found or self.interactive:
                    if not step2_found:
                        self.progress_update.emit(i, f"⚠️ Strict match missed. Fetching fuzzy options...")
                    else:
                        self.progress_update.emit(i, f"➕ Fetching additional fuzzy options...")
                    query = urllib.parse.quote(search_text)
                    search_url = f"https://comicvine.gamespot.com/api/search/?api_key={COMIC_VINE_KEY}&format=json&resources=issue&query={query}&limit=10"
                    time.sleep(1.5)
                    response = requests.get(search_url, headers=headers, timeout=10)
                    fuzzy_data = response.json()
                    if fuzzy_data.get('error') == 'OK':
                        existing_ids = {r['id'] for r in data.get('results', [])}
                        for r in fuzzy_data.get('results', []):
                            if r['id'] not in existing_ids:
                                data['results'].append(r)
                        data['number_of_total_results'] = len(data['results'])

                def _score_issue_result(r):
                    score = 0
                    vol = r.get('volume', {}) or {}
                    vol_name = str(vol.get('name') or '').lower()
                    issue_name = str(r.get('name') or '').lower()
                    issue_num = str(r.get('issue_number') or '')
                    want = series.lower()
                    want_sub = subtitle.lower()

                    lang = str(r.get('language') or '').lower()
                    if lang and lang != 'english':
                        score -= 80

                    _vn = _norm_vol_name(vol_name)
                    _wn = _norm_vol_name(want)
                    if _vn and _vn == _wn:
                        score += 50
                    elif _wn and _wn in _vn:
                        score += 25
                    elif _wn and _vn in _wn:
                        score += 15

                    if year_str:
                        result_year = str(r.get('cover_date', ''))[:4]
                        if result_year == year_str:
                            score += 25
                        elif result_year and result_year != year_str:
                            score -= 20

                    if is_tpb:
                        if target_vol_id and str(vol.get('id', '')) == str(target_vol_id):
                            score += 30
                        if re.search(r'\bvol\.?\s*\d', issue_name, re.I):
                            score += 200
                        if want_sub and want_sub in issue_name:
                            score += 150
                        if vol_num and issue_num == vol_num:
                            score += 100
                        try:
                            if int(r.get('page_count') or 0) > 100:
                                score += 120
                        except (ValueError, TypeError):
                            pass
                        try:
                            n = int(issue_num)
                            if n > 50:
                                score -= 80
                            elif n > 20:
                                score -= 40
                        except (ValueError, TypeError):
                            pass
                    else:
                        if target_vol_id and str(vol.get('id', '')) == str(target_vol_id):
                            score += 60
                        if issue and issue_num == issue:
                            score += 80
                        if want_sub and want_sub in issue_name:
                            score += 40

                    return score

                if data.get('results'):
                    data['results'].sort(key=_score_issue_result, reverse=True)

                if data.get('number_of_total_results', 0) > 0:
                    if self.interactive:
                        local_cover_bytes = b""
                        if is_cbr:
                            temp_dir = tempfile.mkdtemp()
                            try:
                                patoolib.extract_archive(path, outdir=temp_dir, interactive=False)
                                images = sorted([os.path.join(r, f) for r, d, files in os.walk(temp_dir) for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                                if images:
                                    with open(images[0], 'rb') as f:
                                        local_cover_bytes = f.read()
                            except Exception as _e:
                                log.warning("Suppressed exception: %s", _e)
                            finally:
                                if os.path.exists(temp_dir):
                                    shutil.rmtree(temp_dir, onerror=force_remove_readonly)
                        else:
                            try:
                                with zipfile.ZipFile(path, 'r') as zf:
                                    images = sorted([f for f in zf.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                                    if images:
                                        local_cover_bytes = zf.read(images[0])
                            except Exception as _e:
                                log.warning("Suppressed exception: %s", _e)
                        self.user_choice = None
                        self.wait_event.clear()
                        self.needs_confirmation.emit(filename, data['results'], local_cover_bytes)
                        self.wait_event.wait()

                        if not self.user_choice:
                            self.progress_update.emit(i, f"⏭️ Skipped by user: {filename}")
                            continue
                        issue_data = self.user_choice
                    else:
                        issue_data = data['results'][0]

                    api_url = issue_data.get('api_detail_url')
                    if api_url:
                        self.progress_update.emit(i, f"⬇️ Fetching deep metadata (Characters, Arcs) for {filename}...")
                        try:
                            deep_resp = requests.get(f"{api_url}?api_key={COMIC_VINE_KEY}&format=json", headers=headers, timeout=10).json()
                            if deep_resp.get('error') == 'OK':
                                issue_data = deep_resp.get('results', issue_data)
                        except Exception as _e:
                            log.warning("Suppressed exception: %s", _e)

                    comic_info = ET.Element("ComicInfo", {"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance", "xmlns:xsd": "http://www.w3.org/2001/XMLSchema"})

                    m_vol_override = re.search(r'(?i)\b(?:v|vol|volume|book|bk|tpb)\.?\s*0*(\d+)', base_name)
                    local_issue = m_vol_override.group(1) if m_vol_override else issue
                    cv_num = str(issue_data.get('issue_number') or "")
                    final_number = local_issue if (bool(m_vol_override) and local_issue) else (cv_num or local_issue)

                    def _sub(tag, value):
                        v = str(value).strip() if value else ""
                        if v:
                            ET.SubElement(comic_info, tag).text = v

                    _sub("Series", issue_data.get('volume', {}).get('name', series))
                    _sub("Number", final_number)
                    _sub("Title", issue_data.get('name'))
                    _sub("Publisher", issue_data.get('volume', {}).get('publisher', {}).get('name', '') if isinstance(issue_data.get('volume', {}).get('publisher'), dict) else "")
                    _sub("Imprint", issue_data.get('volume', {}).get('imprint') or "")
                    _sub("Format", issue_data.get('format') or "")

                    age = issue_data.get('rating') or issue_data.get('age_rating') or ""
                    _sub("AgeRating", age.get('name', '') if isinstance(age, dict) else age)

                    if issue_data.get('cover_date'):
                        parts = issue_data['cover_date'].split('-')
                        if len(parts) >= 1:
                            _sub("Year", parts[0])
                        if len(parts) >= 2:
                            _sub("Month", parts[1])
                        if len(parts) >= 3:
                            _sub("Day", parts[2])

                    desc = issue_data.get('description') or issue_data.get('deck') or ""
                    cv_summary = re.sub(r'<[^>]+>', '', desc).strip()

                    if not cv_summary and self.ai_summaries and GEMINI_KEY:
                        self.progress_update.emit(i, f"🤖 No CV summary — asking Gemini for: {filename}...")
                        try:
                            from google import genai as _genai
                            from google.genai import types as _gtypes
                            _client = _genai.Client(api_key=GEMINI_KEY)
                            vol_name = issue_data.get('volume', {}).get('name', series)
                            iss_num = issue_data.get('issue_number', issue)
                            iss_name = issue_data.get('name', '')
                            _query = f"{vol_name} #{iss_num}" + (f" — {iss_name}" if iss_name else "")
                            _prompt = (
                                f'Write a 2-3 paragraph plot summary for the comic book "{_query}". '
                                f'Search for accurate plot details. Return ONLY the plain-text summary, nothing else.'
                            )
                            _cfg = _gtypes.GenerateContentConfig(
                                tools=[_gtypes.Tool(google_search=_gtypes.GoogleSearch())]
                            )
                            _resp = _client.models.generate_content(
                                model='gemini-2.5-flash', contents=_prompt, config=_cfg)
                            cv_summary = (_resp.text or "").strip()
                        except Exception as _ae:
                            log.warning("AI summary failed for %s: %s", filename, _ae)

                    _sub("Summary", cv_summary)

                    _sub("PageCount", issue_data.get('page_count') or issue_data.get('number_of_pages') or "")
                    _sub("Web", issue_data.get('site_detail_url') or "")

                    writers, pencillers, inkers, colorists, letterers, cover_artists, editors = [], [], [], [], [], [], []
                    for person in issue_data.get("person_credits", []):
                        roles = person.get("role", "").lower()
                        name = person.get("name", "")
                        if not name:
                            continue
                        if "writer" in roles:
                            writers.append(name)
                        if any(r in roles for r in ["penciler", "penciller"]):
                            pencillers.append(name)
                        if "inker" in roles:
                            inkers.append(name)
                        if "colorist" in roles:
                            colorists.append(name)
                        if "letterer" in roles:
                            letterers.append(name)
                        if "cover" in roles:
                            cover_artists.append(name)
                        if "editor" in roles:
                            editors.append(name)
                        if "artist" in roles and not any(r in roles for r in
                                ["penciler", "penciller", "inker", "colorist", "letterer", "cover", "editor"]):
                            pencillers.append(name)

                    def _dedup(lst):
                        return ", ".join(dict.fromkeys(lst))
                    _sub("Writer", _dedup(writers))
                    _sub("Penciller", _dedup(pencillers))
                    _sub("Inker", _dedup(inkers))
                    _sub("Colorist", _dedup(colorists))
                    _sub("Letterer", _dedup(letterers))
                    _sub("CoverArtist", _dedup(cover_artists))
                    _sub("Editor", _dedup(editors))

                    story_arcs = [str(issue_data.get("story_arc"))] if issue_data.get("story_arc") else []
                    for arc in issue_data.get("story_arc_credits", []):
                        story_arcs.append(arc.get("name", ""))
                    unique_arcs = list(dict.fromkeys(a for a in story_arcs if a))
                    _sub("StoryArc", ", ".join(unique_arcs))

                    _sub("Characters", ", ".join(dict.fromkeys(c['name'] for c in issue_data.get('character_credits', []))))
                    _sub("Teams", ", ".join(dict.fromkeys(t['name'] for t in issue_data.get('team_credits', []))))
                    _sub("Locations", ", ".join(dict.fromkeys(l['name'] for l in issue_data.get('location_credits', []))))

                    ET.SubElement(comic_info, "PlayCount").text = "1"
                    xml_str = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(comic_info, encoding='unicode')

                    written_path = path
                    if is_cbr:
                        self.progress_update.emit(i, f"📦 Extracting {filename}...")
                        temp_dir = tempfile.mkdtemp()
                        try:
                            patoolib.extract_archive(path, outdir=temp_dir, interactive=False)
                            files_to_zip = [os.path.join(r, f) for r, _, files in os.walk(temp_dir) for f in files]
                            new_cbz_path = os.path.splitext(path)[0] + '.cbz'
                            with zipfile.ZipFile(new_cbz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                                for file_path in files_to_zip:
                                    zf.write(file_path, os.path.relpath(file_path, temp_dir))
                                zf.writestr('ComicInfo.xml', xml_str)
                            shutil.rmtree(temp_dir, onerror=force_remove_readonly)
                            os.remove(path)
                            written_path = new_cbz_path
                            self.progress_update.emit(i, f"✅ Converted & Tagged: {os.path.basename(new_cbz_path)}")
                        except Exception as e:
                            self.progress_update.emit(i, f"⚠️ Conversion failed: {str(e)}")
                            if os.path.exists(temp_dir):
                                shutil.rmtree(temp_dir, onerror=force_remove_readonly)
                    else:
                        try:
                            inject_metadata_into_cbz(path, xml_str)
                            self.progress_update.emit(i, f"✅ Tagged: {filename}")
                        except Exception as e:
                            log.warning("BatchTaggerThread CBZ inject failed for %s: %s", filename, e)
                            self.progress_update.emit(i, f"⚠️ Tag failed for {filename}: {e}")

                    if not self.interactive:
                        local_cover_bytes = b""
                        try:
                            with zipfile.ZipFile(written_path, 'r') as zf:
                                imgs = sorted([f for f in zf.namelist()
                                               if f.lower().endswith(('.jpg', '.jpeg', '.png'))
                                               and not f.lower().endswith('comicinfo.xml')])
                                if imgs:
                                    local_cover_bytes = zf.read(imgs[0])
                        except Exception as _e:
                            log.warning("Auto-mode cover read failed: %s", _e)
                        cv_cover_url = ""
                        try:
                            img = issue_data.get('image') or {}
                            cv_cover_url = img.get('medium_url') or img.get('small_url') or img.get('thumb_url') or ""
                        except Exception:
                            pass
                        self._auto_matches.append({
                            'path': written_path,
                            'filename': os.path.basename(written_path),
                            'local_bytes': local_cover_bytes,
                            'issue_data': issue_data,
                            'xml_str': xml_str,
                            'cv_cover_url': cv_cover_url,
                            'is_cbr': False,
                        })
                else:
                    if self.ai_summaries and GEMINI_KEY:
                        self.progress_update.emit(i, f"🤖 No CV match — using AI to tag: {filename}...")
                        try:
                            from google import genai as _genai
                            from google.genai import types as _gtypes
                            _client = _genai.Client(api_key=GEMINI_KEY)
                            _query = f"{series} #{issue} ({year_str})" if issue else f"{series} ({year_str})"
                            _prompt = (
                                f'You are a comic book metadata expert. Generate accurate metadata for "{_query}".\n'
                                'USE GOOGLE SEARCH for accurate details. '
                                'Return ONLY a raw JSON dict (no markdown) with these keys:\n'
                                '{"volume":{"name":""},"issue_number":"","name":"","cover_date":"YYYY-MM-DD",'
                                '"deck":"2-3 paragraph plot summary","story_arc":"",'
                                '"person_credits":[{"name":"","role":"writer"}],'
                                '"character_credits":[{"name":""}]}'
                            )
                            _cfg = _gtypes.GenerateContentConfig(
                                tools=[_gtypes.Tool(google_search=_gtypes.GoogleSearch())]
                            )
                            _resp = _client.models.generate_content(
                                model='gemini-2.5-flash', contents=_prompt, config=_cfg)
                            _text = (_resp.text or "").strip()
                            bt = chr(96) * 3
                            if _text.startswith(bt + "json"):
                                _text = _text[7:].strip()
                            elif _text.startswith(bt):
                                _text = _text[3:].strip()
                            if _text.endswith(bt):
                                _text = _text[:-3].strip()
                            ai_data = json.loads(_text)

                            ai_ci = ET.Element("ComicInfo", {
                                "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                "xmlns:xsd": "http://www.w3.org/2001/XMLSchema"
                            })

                            def _ai_sub(tag, val):
                                v = str(val).strip() if val else ""
                                if v:
                                    ET.SubElement(ai_ci, tag).text = v
                            _ai_sub("Series", (ai_data.get('volume') or {}).get('name') or series)
                            _ai_sub("Number", ai_data.get('issue_number') or issue)
                            _ai_sub("Title", ai_data.get('name'))
                            _ai_sub("Summary", re.sub(r'<[^>]+>', '', ai_data.get('deck') or '').strip())
                            _ai_sub("StoryArc", ai_data.get('story_arc'))
                            if ai_data.get('cover_date'):
                                _pts = ai_data['cover_date'].split('-')
                                if len(_pts) >= 1:
                                    _ai_sub("Year", _pts[0])
                                if len(_pts) >= 2:
                                    _ai_sub("Month", _pts[1])
                            for _p in ai_data.get('person_credits', []):
                                if 'writer' in (_p.get('role') or '').lower():
                                    _ai_sub("Writer", _p.get('name'))
                                    break
                            _ai_sub("Characters", ", ".join(
                                c['name'] for c in ai_data.get('character_credits', []) if c.get('name')))
                            ET.SubElement(ai_ci, "PlayCount").text = "1"
                            ai_xml = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(ai_ci, encoding='unicode')

                            inject_metadata_into_cbz(path, ai_xml)
                            self.progress_update.emit(i, f"🤖 AI tagged: {filename}")
                        except Exception as _ae:
                            log.warning("AI fallback tag failed for %s: %s", filename, _ae)
                            self.progress_update.emit(i, f"❌ No CV match, AI also failed for: {filename}")
                    else:
                        self.progress_update.emit(i, f"❌ No match on Vine for: {filename}")

            except Exception as e:
                self.progress_update.emit(i, f"⚠️ Error tagging {filename}: {str(e)}")
                self.wait_event.set()

        self.progress_update.emit(len(self.file_paths), "🎉 Batch Tagging Complete!")
        if not self.interactive and self._auto_matches:
            self.matches_collected.emit(self._auto_matches)
        self.finished.emit()
