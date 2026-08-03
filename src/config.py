import os
import json
import sys
import logging

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
    "ai_thinking_enabled": True,
    "ai_translate_editable": True,
    "filename_filter_chars": "",
    "slow_speed_threshold": 1,
    "slow_speed_duration": 10,
    "max_slow_restarts": 3,
    "subtitle_convert_enabled": False,
    "auto_flatten_enabled": True,
    "traditional_to_simplified_enabled": True,
}


def _get_app_root():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(current_dir)

_APP_ROOT = _get_app_root()
_USER_ROOT = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else _APP_ROOT
SETTINGS_DIR = os.path.join(_APP_ROOT, "settings")
CONFIG_PATH = os.path.join(SETTINGS_DIR, "config.json")

VERSION = "v1.60.2"

# show_downloaded 模式常量
SHOW_ALL = 1          # 显示全部作品
HIDE_DOWNLOADED = 2   # 隐藏已下载作品
DOWNLOADED_TAB = 3    # 已下载作品 Tab

_cfg = {}
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        _cfg = json.load(f)
except FileNotFoundError:
    pass  # 首次运行，配置文件尚未创建
except Exception as e:
    logging.getLogger(__name__).warning("配置文件解析失败，使用默认配置: %s", e)
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
db_dir_cfg = _cfg["db_dir"]
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

AI_TRANSLATE_ENABLED = _cfg["ai_translate_enabled"]
AI_API_KEY = _cfg["ai_api_key"]
AI_API_BASE_URL = _cfg["ai_api_base_url"]
AI_MODEL = _cfg["ai_model"]
AI_THINKING_ENABLED = _cfg["ai_thinking_enabled"]
AI_TRANSLATE_EDITABLE = _cfg["ai_translate_editable"]

DOWNLOAD_METHOD = _cfg["download_method"]
DIRECT_DOWNLOAD_THREADS = _cfg["direct_download_threads"]
QUEUE_MODE = _cfg["queue_mode"]
MAX_CONCURRENT_DOWNLOADS = _cfg["max_concurrent_downloads"]
FILENAME_FILTER_CHARS = _cfg["filename_filter_chars"]
SLOW_SPEED_THRESHOLD = _cfg["slow_speed_threshold"]
SLOW_SPEED_DURATION = _cfg["slow_speed_duration"]
MAX_SLOW_RESTARTS = _cfg["max_slow_restarts"]
SUBTITLE_CONVERT_ENABLED = _cfg["subtitle_convert_enabled"]
AUTO_FLATTEN_ENABLED = _cfg["auto_flatten_enabled"]
TRADITIONAL_TO_SIMPLIFIED_ENABLED = _cfg["traditional_to_simplified_enabled"]
