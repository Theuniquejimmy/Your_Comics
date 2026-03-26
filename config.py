"""Configuration, constants, and API keys for ComicVault."""
import json
import logging
import os

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    filename='comicvault.log',
    encoding='utf-8',
)
log = logging.getLogger(__name__)

# --- CACHE ---
CACHE_DIR = ".comic_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

_CACHE_VERSION_FILE = os.path.join(CACHE_DIR, ".cache_version")
_REQUIRED_VERSION = "3"
try:
    _current_version = open(_CACHE_VERSION_FILE).read().strip() if os.path.exists(_CACHE_VERSION_FILE) else ""
except Exception:
    _current_version = ""
if _current_version != _REQUIRED_VERSION:
    for _f in os.listdir(CACHE_DIR):
        if _f.startswith("thumb_") and _f.endswith(".jpg"):
            try:
                os.remove(os.path.join(CACHE_DIR, _f))
            except Exception:
                pass
    try:
        open(_CACHE_VERSION_FILE, "w").write(_REQUIRED_VERSION)
    except Exception:
        pass

# --- APP SETTINGS ---
APP_SETTINGS = {
    "cv_key": os.environ.get("COMIC_VINE_KEY", ""),
    "gemini_key": os.environ.get("GEMINI_KEY", ""),
    "reader_path": r"C:\Program Files\YACReader\YACReader.exe",
    "chat_voice": "Christopher (Deep US Male)",
    "chat_speed": 10,
    "cover_size": 250,
    "grid_size": 180,
    "metron_user": "",
    "metron_pass": "",
    "last_dl_dir": "",
    "last_cbl_dir": "",
    "follow_collections": False,
    "theme": "dracula",
}

if os.path.exists("settings.json"):
    try:
        with open("settings.json", "r") as f:
            APP_SETTINGS.update(json.load(f))
    except Exception as _e:
        log.warning("Suppressed exception: %s", _e)

COMIC_VINE_KEY = APP_SETTINGS["cv_key"]
GEMINI_KEY = APP_SETTINGS["gemini_key"]

# --- NEW RELEASES ---
FOLLOWED_SERIES_FILE = "followed_series.json"

PUB_COLOURS = {
    "dc comics": ("#0476D0", "#ffffff", "#0476D0"),
    "marvel comics": ("#FF6B35", "#ffffff", "#FF6B35"),
    "image comics": ("#ef8633", "#282a36", "#ef8633"),
    "dark horse": ("#e7171b", "#ffffff", "#e7171b"),
    "idw publishing": ("#5d4e8c", "#ffffff", "#9b72cf"),
    "boom! studios": ("#00aeef", "#282a36", "#00aeef"),
    "dynamite": ("#c8a227", "#282a36", "#c8a227"),
    "valiant": ("#0d6e6e", "#ffffff", "#1abc9c"),
    "aftershock": ("#ff4500", "#ffffff", "#ff4500"),
    "vault comics": ("#2ecc71", "#282a36", "#2ecc71"),
    "oni press": ("#e74c3c", "#ffffff", "#e74c3c"),
    "titan comics": ("#3498db", "#ffffff", "#3498db"),
    "ablaze": ("#f39c12", "#282a36", "#f39c12"),
}
