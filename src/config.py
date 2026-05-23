import os
import json
import sys

_DEFAULT_CONFIG = {
    "api_url": "https://api.asmr-200.com/api/recommender/recommend-for-user",
    "default_payload": {
        "keyword": " ",
        "localSubtitledWorks": [],
        "page": 1,
        "pageSize": 20,
        "recommenderUuid": "2f912deb-382b-4d16-8644-142e79e65310",
        "subtitle": 0,
        "withPlaylistStatus": []
    },
    "memory_cache_size": 100,
    "aria2_rpc_url": "http://localhost:6800/rpc",
    "download_dir": "downloads",
    "aria2_dir": "aria2",
    "db_dir": "",
    "download_method": "aria2",
    "direct_download_threads": 3,
    "queue_mode": False,
    "max_concurrent_downloads": 1,
    "ai_translate_enabled": False,
    "ai_api_key": "",
    "ai_api_base_url": "https://api.openai.com/v1",
    "ai_model": "gpt-3.5-turbo",
    "ai_translate_editable": True,
    "filename_filter_chars": "",
    "slow_speed_threshold": 1,
    "slow_speed_duration": 10,
    "max_slow_restarts": 3,
}


def _get_app_root():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(current_dir)

_APP_ROOT = _get_app_root()
SETTINGS_DIR = os.path.join(_APP_ROOT, "settings")
CONFIG_PATH = os.path.join(SETTINGS_DIR, "config.json")

VERSION = "v1.33.0"

_cfg = {}
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        _cfg = json.load(f)
except Exception:
    _cfg = {}

for key, default in _DEFAULT_CONFIG.items():
    if key not in _cfg or _cfg[key] is None:
        _cfg[key] = default

API_URL = _cfg["api_url"]
DEFAULT_PAYLOAD = _cfg["default_payload"]
MEMORY_CACHE_SIZE = _cfg["memory_cache_size"]
ARIA2_RPC_URL = _cfg["aria2_rpc_url"]

CONFIG_DIR = SETTINGS_DIR
CACHE_DIR = os.path.join(_APP_ROOT, "image_cache")
db_dir_cfg = _cfg.get("db_dir", "")
if db_dir_cfg:
    DB_DIR = db_dir_cfg if os.path.isabs(db_dir_cfg) else os.path.join(_APP_ROOT, db_dir_cfg)
else:
    DB_DIR = SETTINGS_DIR
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "works.db")
DOWNLOAD_HISTORY_DB_PATH = os.path.join(DB_DIR, "download_history.db")
ICON_PATH = os.path.join(SETTINGS_DIR, "ui.ico")
download_dir_cfg = _cfg["download_dir"]
DOWNLOAD_DIR = download_dir_cfg if os.path.isabs(download_dir_cfg) else os.path.join(_APP_ROOT, download_dir_cfg)
aria2_dir_cfg = _cfg["aria2_dir"]
ARIA2_DIR = aria2_dir_cfg if os.path.isabs(aria2_dir_cfg) else os.path.join(_APP_ROOT, aria2_dir_cfg)

AI_TRANSLATE_ENABLED = _cfg.get("ai_translate_enabled", False)
AI_API_KEY = _cfg.get("ai_api_key", "")
AI_API_BASE_URL = _cfg.get("ai_api_base_url", "https://api.openai.com/v1")
AI_MODEL = _cfg.get("ai_model", "gpt-3.5-turbo")
AI_TRANSLATE_EDITABLE = _cfg.get("ai_translate_editable", True)

DOWNLOAD_METHOD = _cfg.get("download_method", "aria2")
DIRECT_DOWNLOAD_THREADS = _cfg.get("direct_download_threads", 3)
QUEUE_MODE = _cfg.get("queue_mode", False)
MAX_CONCURRENT_DOWNLOADS = _cfg.get("max_concurrent_downloads", 1)
FILENAME_FILTER_CHARS = _cfg.get("filename_filter_chars", "")
SLOW_SPEED_THRESHOLD = _cfg.get("slow_speed_threshold", 1)
SLOW_SPEED_DURATION = _cfg.get("slow_speed_duration", 10)
MAX_SLOW_RESTARTS = _cfg.get("max_slow_restarts", 3)